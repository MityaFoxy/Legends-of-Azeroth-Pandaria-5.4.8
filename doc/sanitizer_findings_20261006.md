# ASan/UBSan findings from allocator-soak-20261006-r3

## r13 map-script lifetime findings (2026-10-08)

The 100-bot stage completed ten hours, then the scheduled shutdown exited 1.
Console UBSan findings occurred in ScriptMgr::OnCreateMap, OnMapUpdate and
OnDestroyMap (pre-fix lines 486/594/503). A dungeon DBC entry was used as proof
that a Map pointer addressed an InstanceMap. The reset scheduler actually
created a MapInstanced container; its base constructor/destructor had dynamic
type Map, and its update had dynamic type MapInstanced, neither InstanceMap.
LSan reported 48 bytes in six allocations, all from __cxa_demangle through
UBSan diagnostic rendering. Do not suppress them: verify again after the
underlying downcast fix. No lost-owner GameObject FATAL was observed in r13.

Working-tree repair: dispatch all seven map hook families only through a
checked dynamic type; containers do not receive instance/BG hooks. Preserve
world-map hooks in Map, but invoke instance/BG create hooks at the end of their
derived constructors and destroy hooks at the beginning of their destructors,
before instance data/BG references are torn down. DBC selection and one callback
per matching registry entry remain unchanged; no schema or terrain-format change.

map_script_regression.py extracts the actual dispatcher, reproduces the old
UBSan downcast and verifies all seven hooks for world/instance/BG maps and
rejection of base/container impostors. It also checks real source lifecycle
placement. These doubles/source checks do not replace runtime instance creation,
teardown and another full soak. Full validation and commit remain pending.

Both normal/mimalloc and diagnostic binaries compiled. Normal 25/50/100-bot
stages exited zero; the 100-bot stage ran 30 minutes. Diagnostic 25-bot stage
reached its target and ran five minutes, then shutdown failed at 16:27 UTC.
Neither diagnostic 50/100-bot stages nor the overnight interval ran.

## Confirmed causes and repairs in the working tree

| Area | Before | After / reason |
| --- | --- | --- |
| Battlefield graveyards | Derived BfGraveyardWG deleted through base without virtual destructor; ASan reports allocated88/deleted80 bytes | Virtual base destructor dispatches correct destruction |
| SQL Field, DBC/DB2 loaders | Typed dereferences into packed byte buffers | memcpy-based Read/WriteUnaligned helpers; offsets and stored bytes unchanged |
| Object update fields | uint64/ObjectGuid pointer casts into uint32 array, including odd indices | Explicit low/high32 reconstruction and writes; same two fields and update-mask notifications |
| Runtime locale records and PageText | STL objects under pack(1), yielding misaligned members in map nodes | Move STL-containing types outside packing; leave binary records and TempSummonGroupKey comparator unchanged |
| Invisibility |38types in32-bit flags, bit36 invalid/colliding |64-bit unsigned flags for invisibility and its detection; template width assertion and unsigned shifts |
| Mechanics/aura states/stances/SmartAI phase |1-based bit shifts with zero/invalid ID, including -1; SmartAI phase decrement could underflow | Zero mask for ID0/out-of-range; valid IDs1..32 retain their bits; clamp phase decrement at0 |
| Group member ready-check |bool copied before initialized |Default false for newly constructed MemberSlot |
| SpellGroup |Unfixed enum named0..5 used with legitimate DB IDs1000+ |Explicit uint32 underlying type accepts DB range without changing stored IDs |
| Detour links |64-bit dtLink requires8-byte alignment but existing mmap sections align4 |Explicit pack4 for dtLink, sizeof remains16; no map regeneration or file-layout change |

Standalone ASan/UBSan regression test uses the actual new helpers, flag template
and Detour header. It exercises byte offsets1..7, integer/float/pointer roundtrip,
mask IDs0/1/32/33/UINT_MAX, invisibility bits0..37 including non-collision36/4,
and dtLink at a4-byte but not8-byte boundary. Passed before full server rebuild.
This does not replace real startup/gameplay/shutdown coverage.

## Provenance and remaining verification

Read-only comparison with pre-merge commit
738b5dd2861b8743c959b899a1aae742869aeec3 confirms missing BfGraveyard destructor,
the32-bit invisibility flags and Field::GetUInt64 typed pointer read already
existed before the merge. No blanket claim is made for other findings.

No DB rows, schemas, mmap blobs, DBC formats or network field layouts are migrated.
Internal object sizes/alignment do change and require rebuilding dependent code.
Do not use sanitizer suppressions to call the run clean. The runner checks
recovering UBSan findings as well as exit codes before advancing stages.
Full rebuilt server and renewed load test remain pending until events record them.
# Повторная проверка 7 октября: r4 и ручной вход

Сборка r4 ASan/UBSan завершилась. Этап с 25 ботами остановился с кодом 1
при завершении сервера. Повторный ручной запуск с 25 ботами, во время которого
пользователь заходил за двух персонажей, воспроизвёл ту же ошибку при SIGTERM.
Это не устанавливает причинную связь ошибок с пользовательскими входами.
Оба запуска не дошли до 12-часового этапа. Артефакты: `allocator-soak-20261006-r4`
и `sanitizer-manual-25-20261007-0010` в runtime.

| Место | Было | Исправление и причина |
| --- | --- | --- |
| BattlegroundQueue / SoloQueue | Производный объект размером 4040 удалялся как базовый размером 3456 | Виртуальный деструктор базовой очереди сохраняет полное уничтожение SoloQueue через unique_ptr базового типа |
| WorldObject::~WorldObject | IsWorldObject/ResetMap обращались к Creature после завершения производного деструктора | Очистка напрямую удаляет указатель из набора объектов карты; erase отсутствующего указателя безопасен. Исключено и обращение к производному Corpse в сообщении об ошибке |
| MemoryCalculatedValue | Предыдущее значение, а также кеш CalculatedValue могли быть неинициализированы; Set игнорировал аргумент | Инициализация T{}, передача реального аргумента Set. Это сохраняет сравнение изменений, устраняя чтение неопределённого bool и потерю записываемого значения |
| Кеш имён | Категория таблицы 14 преобразовывалась в Gender с допустимыми значениями 0..3 | Ключ uint8 сохраняет все исходные категории. Выбор мужского/женского имени остаётся по ключам 0/1; строки БД не меняются |
| SetHolidayWeekends | Сдвиг int на 32 и больше для высоких ID полей боя | Ограниченная unsigned-маска: исходные битовые позиции 1..31 сохранены, ID >=32 не может быть представлен существующим uint32 mask и получает false, без заворачивания к младшим битам |

Добавлен `lifecycle_regression.py`: извлекает реальные тела методов/шаблонов
из исходников и выполняет их с небольшими заглушками карты и очереди под ASan/UBSan.
Проверяет виртуальное уничтожение, очистку карты для обычного/временного/постоянного
объекта, bool и Set, граничные праздничные маски и категорию имён 14.
Это точечная проверка, не замена полной сборке и игровому прогону.
Первоначальные два CTest прошли; полная повторная сборка/остановка ещё не проверены.
Отдельный lost-owner FATAL GameObject остаётся нерешённым.

## LeakSanitizer: r5 и исправления для r6 (7 октября)

Контрольный `allocator-soak-20261007-r5` собрался, достиг 25 online ботов,
прошёл пять минут нагрузки и завершился с кодом 1 при SIGTERM. LeakSanitizer
сообщил `1782284 byte(s) leaked in 54915 allocation(s)`; отчёт содержит
предупреждение о лимите первых 5000 записей утечек. Это не 54915 независимых
причин: большая часть выделений принадлежит нескольким потерянным владельцам.
Старые new/delete mismatch и сообщения `runtime error:` в проверенных логах
этого запуска не повторились. Ночной этап не запускался.

| Место | Было | Стало и обоснование |
| --- | --- | --- |
| Boost items | Вектор сырых указателей очищался без delete; невалидная строка также теряла объект | Простые записи хранятся по значению, без отдельного new. Хранилище перенесено из header в единственный cpp; выдача предметов остаётся прежней |
| RetroactiveFix | Статические объекты сервисных исправлений не освобождались, базовый тип не имел виртуального деструктора | unique_ptr и виртуальный деструктор. Набор и порядок исправлений не меняются |
| ScriptMgr | При Unload пропущены SpellAreaTriggerScript, GlobalScript и PlayerbotScript | Все три реестра очищаются штатным SCR_CLEAR; сценарии не отключаются и продолжают действовать до остановки |
| SmartWaypointMgr | Маршруты и точки освобождались при reload, но деструктор очистку не выполнял | Общая Clear вызывается и при reload, и в деструкторе; двойной вызов безопасен |
| Wild battle pets | Депопуляция вызывалась в Map::~Map после первого UnloadAll, когда оригиналы уже исчезли; потерянный оригинал препятствовал удалению замены. Стиралась связь по replacement GUID вместо original GUID | Депопуляция конкретной карты выполняется до выгрузки сеток; замены удаляются штатным remove-list. Связь стирается по правильному ключу, отсутствие оригинала не блокирует очистку. Изменены обходы контейнера, чтобы erase не инвалидировал используемый итератор |
| BattlePet state | Карта WildBattlePetInfo содержала сырые указатели; остаточные записи и их способности терялись | unique_ptr, move-only передача шаблонов и очистка при удалении связи. Ошибка AddToMap также освобождает замену и её состояние, не деспавнит оригинал |
| Playerbots | Registry erase не удалял AI/менеджер. LogoutPlayerBot заранее удалял holder-entry, поэтому DisablePlayerBot уже не находил AI. Ручное delete могло оставить висячую registry-entry | Реестры владеют unique_ptr; logout-hook очищает обе категории до удаления Player, независимо от holder. Disable использует тот же реестр. Убран рекурсивный erase из деструктора менеджера. Виртуальные деструкторы PlayerbotAIBase и NamedObjectFactory обеспечивают полное уничтожение производных объектов |
| Player::AddSpell | Обучение нижнего ранга через SetSkill могло рекурсивно обучить текущий; внешний вызов затем перезаписывал указатель в m_spells | После обучения нижнего ранга повторно проверяется наличие текущего. Для уже созданной записи используются обычные existing-spell правила, сохраняя запрошенные флаги и не дублируя дальнейшие эффекты обучения |

Добавлена `leak_regression.py`: реальные объявления и тела функций проверяются
с небольшими подсистемными заглушками под ASan/UBSan/LSan. Покрыты повторная
очистка маршрутов, удаление замен при отсутствующих оригиналах/заменах,
освобождение остаточного состояния, повторная регистрация AI, идемпотентный
logout-hook и рекурсивное обучение ранга. Проверяются полнота очистки
реестров и порядок удаления питомцев относительно выгрузки сеток.
Все три CTest прошли. Запуск новой регрессии на HEAD до этих исправлений
ожидаемо падает на трёх пропущенных реестрах.

Полная сборка r6 и реальный прогон/остановка ещё выполняются. Нельзя считать
все утечки закрытыми до чистого отчёта: лимит r5 мог скрыть следующие группы.
Нужна также игровая проверка боёв питомцев и обычного входа/выхода персонажа;
заглушки не доказывают правильность всех игровых взаимодействий.
Данные/схемы БД, постоянные конфиги и normal runtime-бинарники не менялись.
Изменились внутреннее владение и vtable; зависимые части сервера пересобираются.

## Оставшиеся утечки r6 и исправления для r7

Сборка r6 завершилась успешно. После пяти минут с 25 online ботами штатная
остановка закончилась с кодом 1 в 01:56 МСК 7 октября. LeakSanitizer сообщил
`27808 byte(s) leaked in 620 allocation(s)`; прежнего ограничения на первые
5000 записей в этом отчёте уже нет. Это существенно меньше r5, но не чистый
результат. Автоматическое ночное продолжение корректно отказалось запускаться.

| Место | Причина | Исправление |
| --- | --- | --- |
| Map-owned corpses | ObjectGridUnloader намеренно не удаляет Corpse: владельцем является Map. Однако Map::~Map только отсоединял world objects, а трупы в ещё не загруженных сетках также оставались в owning-индексах | UnloadCorpseData удаляет трупы и кости через RemoveCorpse, затем освобождает объекты и индекс ячеек. Вызов при уничтожении карты; SQL DeleteCorpseData/DeleteFromDB не вызываются, сохранённые GUID и строки БД остаются прежними |
| SmartScript::GetTargetList | Новый ObjectList с узлами списка возвращался сырым указателем; оба escort-вызова и SEND_TARGET_TO_TARGET забывали его освободить, в том числе при ранних return | Возврат unique_ptr и владение во всех трёх вызывающих местах. Удаляется контейнер, а не заимствованные WorldObject; разрешение GUID, порядок целей, nullptr и пустой список сохраняются |
| Spell/Aura script startup allocations | Семь прямых new создавали не loader, а runtime SpellScript/AuraScript, который нигде не регистрировался и не имел владельца | Убраны прямые new для mage evocation, paladin avenging wrath/double jeopardy judgment, priest devouring plague, warlock soul link, Unsok reshape of life. Их существующие корректные aura_script/spell_script регистрации сохранены ровно по одной |
| Protection of Elune | Прямой new также создавал не зарегистрированный AuraScript; привязка 38528 ранее была помещена в disabled archive | Убран неиспользуемый new, а не восстановлена устаревшая привязка. Read-only проверка текущей БД: active=0, archived=1. Скрипт остаётся отключённым |

Новая `cleanup_regression.py` выполняет реальные тела UnloadCorpseData,
RemoveCorpse и GetTargetList на небольших заглушках. Проверяет 1000 циклов
очистки трупов/костей в загруженных и незагруженных сетках, повторную очистку,
удаление через деструктор, отсутствующие GUID, пустые списки, ранний return,
AreaTrigger fallback и сохранность заимствованных WorldObject. Проверяет
однократные правильные регистрации и отсутствие восстановления Elune.
Все четыре CTest прошли, включая повтор после уточнения disabled Elune.
Полная r7 сборка и runtime shutdown ещё нужны;
закрытие всех утечек этим документом не утверждается.

## r7: 160 байт и исправления для r8

r7 собрался и выполнил пяти минутный контрольный этап с 25 online ботами.
Остановка в 08:51 МСК 7 октября завершилась с кодом 1: LeakSanitizer сообщает
160 байт в четырёх выделениях. Ночной этап снова корректно не запущен.

Два BlackMarketAuction (112 байт) выделены в LoadAuctions, но теряются в
Update при истечении срока: erase удалял только запись контейнера.
Добавлен delete после SendAuctionWon/DeleteFromDB и erase. Порядок выдачи
предмета/письма и SQL-транзакции не меняется; активные аукционы остаются в
контейнере. SendAuctionWon формирует MailSender по значению и не сохраняет
указатель на Auction для отложенного выполнения.

Остальные 48 байт — список и его узел из GetTargets в SMART_ACTION_WP_START.
StoreTargetList копирует GUID, но не владеет входным списком. Для WP_START
входной список теперь хранится в unique_ptr. В SEND_TARGET_TO_TARGET также
убраны лишние new ObjectList: получателям передаётся заимствованный указатель,
каждый самостоятельно копирует GUID. StoreTargetList принимает const pointer,
явно документируя отсутствие передачи владения. WorldObject не удаляются,
порядок/повторы GUID, фильтрация nullptr и обработка пустого ввода сохраняются.

Добавлена auction_target_regression.py с реальным телом BlackMarketMgr::Update,
StoreTargetList и фрагментом владения WP_START. В 1000 циклах проверяются
истечение первого/среднего/последнего элемента, аукционы с победителем и без,
сохранение активных аукционов, порядок выдачи/удаления, повторный Update,
копирование GUID нескольким получателям, nullptr и повторяющиеся цели.
Все пять CTest прошли под ASan/UBSan/LSan. Полный повтор r8 ещё требуется;
чистая остановка и 12-часовая нагрузка не объявляются завершёнными.

## r8/r9: чистые короткие этапы, resource-stop и исправление для r10

r8 завершил контроль с 25 ботами и exit code 0 без sanitizer findings.
r9-night повторил чистые 25/50 этапы, достиг 100 ботов в 11:36:24 UTC
7 октября, но в 11:39:25 UTC остановлен по порогу памяти: доступно
763756544 байт при пороге 805306368. RSS worldserver — 7409909760 байт;
swap практически исчерпан. Это не завершённый 12-часовой тест.
При shutdown снова записан lost-owner FATAL для GO 188215 / Spell 46905,
владелец creature GUID 534064. Сообщения ASan/UBSan в этом запуске не найдены.

Было: EffectTransmitted регистрировал только fishing node, player ritual
и duel arbiter, а остальным и linked GO просто записывал OwnerGUID.
Unit::RemoveAllGameObjects не видел такие объекты при очистке владельца.
Стало: основной и linked объекты однократно регистрируются через
Unit::AddGameObject. Это одновременно задаёт OwnerGUID и добавляет объект
в список очистки. Специальные ветки больше не регистрируют его отдельно.
GameObject::RemoveFromOwner и его FATAL не изменены.

Позиции, фазы, транспорт, SpellId и формулы duration/respawn сохранены.
Для основного объекта регистрация остаётся до SetSpellId, как раньше
для специальных типов, поэтому не добавляется SetCooldownOnHold.
Linked объект также регистрируется до SetSpellId: раньше он вообще не
регистрировался и этот side effect не выполнялся. Теперь при удалении
владельца его объекты получают штатную очистку вместо потерянной ссылки;
это намеренное изменение lifetime при teardown владельца, не изменение
таймера существующего объекта. Поведение удаления аур/cooldown в Unit
не переписывается. Отдельный raw-owner путь успешной рыбалки не затронут.

gameobject_owner_regression.py извлекает реальный хвост EffectTransmitted
и тела Unit::AddGameObject/RemoveAllGameObjects, используя тестовые doubles
для остального окружения. Проверяет player/creature, шесть типов GO,
linked/no-linked, ошибку создания linked, нулевую/положительную duration,
однократную регистрацию, сохранение fishing channel/timers/SpellId,
отсутствие нового cooldown hold и повторную очистку. Все шесть CTest прошли
под ASan/UBSan/LSan. Это не заменяет runtime/gameplay-проверку: настоящий
Map teardown, ловля рыбы, ритуалы и cooldown события требуют интеграции.
Runner теперь отклоняет lost-owner findings даже при exit code 0.
Следующий контролируемый запуск: r10; успешный контроль разрешает r11-night.
Пороги RAM/disk/logs и параметры санитайзеров не ослаблены.

## r12: остановка из-за suspend хоста, исправление автоматики

После освобождения памяти и согласованного порога RAM 512 MiB r12 достиг
100 онлайн-ботов в 20:17:08 МСК 7 октября и сохранял число 100 во всех
полученных замерах до 01:01:04 МСК 8 октября. В 01:01:34 runner зафиксировал
ошибку диагностического запроса MySQL. До этого ресурсного порога не достигал:
последние available RAM 4475494400 байт, free swap 1657126912 байт.
Максимальный RSS за этап — 8556703744 байт. Полный 12-часовой результат
не получен; код выхода worldserver старый обработчик не записал.

Причина на хосте: systemd-logind записал suspend requested от csd-power
в 01:01:34, NetworkManager отключил сеть в ту же секунду. Ядро вошло в
s2idle в 01:01:35; проснулось в 01:39:46. Заморозка user.slice объясняет
длительную паузу до выхода ботов в 01:39:59. После пробуждения БД доступна,
живого worldserver больше нет. В проверенных console.log не обнаружены
ASan/UBSan/LSan/lost-owner FATAL; отдельных ненулевых asan/ubsan reports нет.
Это не доказательство 12-часовой стабильности или известного exit code 0.

Исправления только в диагностике: новый host launcher держит sleep:idle
inhibitor до выхода foreground podman exec; SQL ограничен timeout и тремя
попытками только временных connection failures, stderr сохраняется;
terminal failed теперь записывается после cleanup и сообщает exit_code/
still_alive. Постоянные power settings, игровая логика и SQL-схемы не меняются.
Новый soak_controller_regression проверяет transient recovery, timeout,
постоянный сбой, отсутствие повторов ошибок схемы/некорректного ответа,
редактирование пароля, сохранность resource guard и shutdown observability.
Восемь Python-проверок прошли; интеграционный повтор с inhibitor ещё нужен.
