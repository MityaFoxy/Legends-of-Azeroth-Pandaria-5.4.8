# ASan/UBSan findings from allocator-soak-20261006-r3

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
