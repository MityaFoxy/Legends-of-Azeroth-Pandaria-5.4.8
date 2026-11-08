// Opt-in native fixture. No spells, talents, equipment or cooldowns are granted.
#include "DruidControlTest.h"
#include "Action.h"
#include "ActionExecutionTrace.h"
#include "AiObjectContext.h"
#include "CharacterCache.h"
#include "Chat.h"
#include "Config.h"
#include "Group.h"
#include "GroupMgr.h"
#include "Map.h"
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "PlayerbotMgr.h"
#include "RandomPlayerbotMgr.h"
#include "ScriptMgr.h"
#include "Spell.h"
#include "TemporarySummon.h"
#include "Trigger.h"
#include <sstream>

namespace
{
class DruidControlTest : public WorldScript
{
    struct Member { ObjectGuid guid; uint32 map = 0, health = 0, phase = 0; Position pos; bool saved = false; };
    std::vector<Member> _members;
    ObjectGuid _beast, _human;
    Group* _group = nullptr;
    uint32 _elapsed = 0, _next = 0, _phase = 0;
    std::string _rti;
    std::string _originalStrategies;
    GuidVector _prioritized;
    bool _prepared = false;
    bool _strategyChanged = false;
    bool _groupGcdObserved = false;
public:
    DruidControlTest() : WorldScript("playerbot_druid_control_test") {}
    bool Start(std::vector<ObjectGuid> const& guids)
    {
        if (!_members.empty()) return false;
        _elapsed = _next = _phase = 0;
        _prepared = false;
        _strategyChanged = false;
        _groupGcdObserved = false;
        for (auto guid : guids)
        {
            _members.push_back({guid});
            if (!sRandomPlayerbotMgr->GetPlayerBot(guid)) sRandomPlayerbotMgr->AddPlayerBot(guid, 0);
        }
        TC_LOG_INFO("playerbots", "Control fixture started guid={}", guids.front().GetCounter());
        return true;
    }
    void Finish(bool passed, char const* reason)
    {
        if (_members.empty()) return;
        Player* bot = sRandomPlayerbotMgr->GetPlayerBot(_members.front().guid);
        if (bot)
        {
            if (_prepared) bot->InterruptNonMeleeSpells(false);
            for (auto guid : {_beast, _human})
                if (Creature* npc = bot->GetMap()->GetCreature(guid))
                {
                    npc->CombatStop(true);
                    npc->DespawnOrUnsummon();
                }
            if (auto* ai = sPlayerbotsMgr->GetPlayerbotAI(bot); ai && _prepared)
            {
                auto* ctx = ai->GetAiObjectContext();
                ctx->GetValue<std::string>("rti cc")->Set(_rti);
                ctx->GetValue<GuidVector>("prioritized targets")->Set(_prioritized);
                ctx->GetValue<Unit*>("current target")->Set(nullptr);
                if (_strategyChanged)
                {
                    ai->ClearStrategies(BOT_STATE_COMBAT);
                    ai->ChangeStrategy(_originalStrategies, BOT_STATE_COMBAT);
                }
            }
        }
        if (_group) { Group* group = _group; _group = nullptr; group->Disband(); }
        for (auto const& member : _members)
            if (Player* p = sRandomPlayerbotMgr->GetPlayerBot(member.guid))
            {
                p->CombatStop(true);
                if (bot)
                    for (uint32 id : {774, 44203}) p->RemoveAurasDueToSpell(id, bot->GetGUID());
                if (member.saved)
                {
                    p->SetHealth(member.health);
                    p->SetPhaseMask(member.phase, true);
                    if (p != bot) p->TeleportTo(member.map, member.pos.m_positionX, member.pos.m_positionY,
                        member.pos.m_positionZ, member.pos.m_orientation);
                }
                if (auto* ai = sPlayerbotsMgr->GetPlayerbotAI(p)) ai->SetNextCheckDelay(120000);
            }
        TC_LOG_INFO("playerbots", "Control fixture finished guid={} passed={} phase={} reason={} cleanup=done combat={}",
            _members.front().guid.GetCounter(), passed, _phase, reason, bot && bot->IsInCombat());
        _members.clear();
    }
    void OnShutdownInitiate(ShutdownExitCode, ShutdownMask) override { Finish(false, "shutdown"); }
    void OnShutdown() override { Finish(false, "shutdown"); }
    void OnUpdate(uint32 diff) override
    {
        if (_members.empty()) return;
        _elapsed += diff;
        if (_elapsed > 240000) { Finish(false, "timeout"); return; }
        std::vector<Player*> players;
        for (auto const& member : _members)
        {
            Player* p = sRandomPlayerbotMgr->GetPlayerBot(member.guid);
            auto* ai = p ? sPlayerbotsMgr->GetPlayerbotAI(p) : nullptr;
            if (ai) ai->SetNextCheckDelay(120000);
            if (!p || !ai || !p->IsInWorld() || p->IsBeingTeleported()) return;
            players.push_back(p);
        }
        Player* bot = players.front();
        auto* ai = sPlayerbotsMgr->GetPlayerbotAI(bot);
        auto* ctx = ai->GetAiObjectContext();
        auto check = [&](bool ok, char const* reason) {
            if (!ok) Finish(false, reason);
            return ok;
        };
        if (!_prepared)
        {
            for (auto* p : players)
                if (!check(p->GetClass() == CLASS_DRUID && p->IsAlive() && !p->GetGroup() &&
                    !p->InBattleground() && !p->IsInCombat() && !p->IsMounted() && !p->IsFlying() &&
                    !p->IsInFlight() && !sPlayerbotsMgr->GetPlayerbotAI(p)->IsRealPlayer(), "player preconditions")) return;
            for (uint32 id : {339, 2637, 5211, 132158, 5185, 774, 740})
                if (!check(bot->HasSpell(id), "existing leader spellbook")) return;
            if (!check(!bot->HasAura(132158), "preexisting Swift")) return;
            for (size_t i = 0; i < players.size(); ++i)
            {
                auto& saved = _members[i];
                saved.map = players[i]->GetMapId(); saved.pos.Relocate(players[i]);
                saved.health = players[i]->GetHealth(); saved.saved = true;
                saved.phase = players[i]->GetPhaseMask();
                players[i]->StopMoving();
            }
            _rti = ctx->GetValue<std::string>("rti cc")->Get();
            _prioritized = ctx->GetValue<GuidVector>("prioritized targets")->Get();
            ctx->GetValue<std::string>("rti cc")->Set("moon");
            ctx->GetValue<Unit*>("current target")->Set(nullptr);
            _prepared = true;
            if (bot->GetShapeshiftForm() != FORM_NONE &&
                !check(ctx->GetAction("caster form")->Execute(Event()), "initial form")) return;
            for (size_t i = 1; i < players.size(); ++i)
                if (!check(players[i]->TeleportTo(bot->GetMapId(), bot->GetPositionX(), bot->GetPositionY(),
                    bot->GetPositionZ(), bot->GetOrientation()), "party teleport")) return;
            _next = _elapsed + 2500;
            return;
        }
        if (_elapsed < _next) return;
        auto active = [&](char const* name) { auto* t = ctx->GetTrigger(name); return t && t->IsActive(); };
        auto action = [&](char const* name) { return ctx->GetAction(name); };
        auto cast = [&](char const* name) {
            Action* a = action(name);
            TC_LOG_INFO("playerbots", "Control fixture action={} target={} useful={} possible={}", name,
                a && a->GetTarget() ? a->GetTarget()->GetGUID().ToString() : "none",
                a && a->isUseful(), a && a->isPossible());
            if (!a || !a->isUseful() || !a->isPossible()) return false;
            ActionExecutionTrace trace(true);
            bool result = a->Execute(Event());
            trace.Finish(bot, a, result, result);
            return result;
        };
        auto healReset = [&] {
            ctx->GetValue<Unit*>("party member to heal")->Reset();
            ctx->GetValue<uint8>("health", "party member to heal")->Reset();
            ctx->GetValue<bool>("dead", "party member to heal")->Reset();
            ctx->GetValue<uint8>("aoe heal", "almost full")->Reset();
            ctx->GetValue<uint8>("aoe heal", "medium")->Reset();
        };
        Creature* beast = bot->GetMap()->GetCreature(_beast);
        Creature* human = bot->GetMap()->GetCreature(_human);
        if (_phase && !check(beast && human && bot->IsAlive(), "fixture creatures")) return;
        if (beast)
            TC_LOG_INFO("playerbots", "Control fixture state phase={} alive={} hp={} combat={} root={} sleep={} stun={} caster_casting={} caster_moving={} caster_form={} target_xyz={},{},{}",
                _phase, beast->IsAlive(), beast->GetHealth(), beast->IsInCombat(), beast->HasAura(339, bot->GetGUID()),
                beast->HasAura(2637, bot->GetGUID()), beast->HasAura(5211, bot->GetGUID()),
                bot->IsNonMeleeSpellCasted(true), bot->isMoving(), uint32(bot->GetShapeshiftForm()),
                beast->GetPositionX(), beast->GetPositionY(), beast->GetPositionZ());
        _next = _elapsed + 3000;
        switch (_phase)
        {
            case 0:
            {
                _group = new Group();
                if (!_group->Create(bot)) { delete _group; _group = nullptr; Finish(false, "group creation"); return; }
                sGroupMgr->AddGroup(_group);
                for (size_t i = 1; i < players.size(); ++i)
                    if (!check(_group->AddMember(players[i]), "group membership")) return;
                // Teleport/area processing restores normal phases. Isolate the
                // whole party only after every arrival has completed.
                for (auto* p : players) p->SetPhaseMask(0x40000000, true);
                Position pos;
                bot->GetNearPoint(nullptr, pos.m_positionX, pos.m_positionY, pos.m_positionZ, 2.0f, bot->GetOrientation());
                for (uint32 entry : {30, 38})
                {
                    auto* npc = bot->GetMap()->SummonCreature(entry, pos, nullptr, 260s);
                    if (!check(npc != nullptr, "summon")) return;
                    npc->SetTempSummonType(TEMPSUMMON_TIMED_DESPAWN);
                    npc->SetPhaseMask(bot->GetPhaseMask(), true); npc->IsAIEnabled = false;
                    npc->SetReactState(REACT_PASSIVE); npc->SetFaction(14);
                    // Only the disposable caster's power is setup data.
                    npc->SetPowerType(POWER_MANA); npc->SetMaxPower(POWER_MANA, 100000); npc->SetPower(POWER_MANA, 100000);
                    (entry == 30 ? _beast : _human) = npc->GetGUID();
                }
                if (!check(!active("entangling roots") && !action("hibernate on cc")->Execute(Event()), "no assignment")) return;
                _group->SetTargetIcon(4, bot->GetGUID(), _beast, 0);
                if (!check(active("entangling roots") && cast("entangling roots on cc"), "root chain")) return;
                break;
            }
            case 1:
                if (!check(beast->HasAura(339, bot->GetGUID()) && !active("hibernate"), "native root and CC guard")) return;
                beast->RemoveAurasDueToSpell(339, bot->GetGUID());
                _group->SetTargetIcon(4, bot->GetGUID(), _human, 0);
                if (!check(!active("hibernate") && !action("hibernate on cc")->Execute(Event()), "humanoid exclusion")) return;
                _group->SetTargetIcon(4, bot->GetGUID(), _beast, 0);
                if (!check(active("hibernate") && cast("hibernate on cc"), "Hibernate chain")) return;
                break;
            case 2:
                if (!check(beast->HasAura(2637, bot->GetGUID()) && !active("entangling roots"), "native sleep and repeat guard")) return;
                beast->RemoveAurasDueToSpell(2637, bot->GetGUID());
                ctx->GetValue<Unit*>("current target")->Set(beast);
                if (!check(!active("entangling roots"), "current attack target exclusion")) return;
                ctx->GetValue<Unit*>("current target")->Set(nullptr);
                if (!check(cast("cat form"), "native Cat Form")) return;
                break;
            case 3:
            {
                NextAction** prerequisites = action("entangling roots on cc")->getPrerequisites();
                bool caster = prerequisites && prerequisites[0]->getName() == "caster form";
                NextAction::destroy(prerequisites);
                if (!check(bot->GetShapeshiftForm() == FORM_CAT && caster && cast("caster form"), "native shapeshift prerequisite")) return;
                break;
            }
            case 4:
                if (!check(bot->GetShapeshiftForm() == FORM_NONE && cast("entangling roots on cc"), "post-prerequisite root")) return;
                break;
            case 5:
                if (!check(beast->HasAura(339, bot->GetGUID()), "post-prerequisite effect")) return;
                beast->RemoveAurasDueToSpell(339, bot->GetGUID());
                ctx->GetValue<Unit*>("current target")->Set(beast);
                if (!check(!active("bash"), "noncasting Bash guard")) return;
                beast->CastSpell(beast, 5185, false);
                if (!check(beast->IsNonMeleeSpellCasted(true) && active("bash") && cast("bash"), "primary Bash chain")) return;
                _next = _elapsed + 1000;
                break;
            case 6:
                if (!check(beast->HasAura(5211, bot->GetGUID()) && !beast->IsNonMeleeSpellCasted(true), "native Bash stun and cast stop")) return;
                TC_LOG_INFO("playerbots", "Control fixture native effects root=339 sleep=2637 stun=5211 cast_stopped=true");
                // Wait out the real 50 s talent cooldown, never clear it.
                _next = _elapsed + 65000;
                break;
            case 7:
                ctx->GetValue<Unit*>("current target")->Set(human);
                ctx->GetValue<GuidVector>("prioritized targets")->Set({_beast});
                ctx->GetValue<GuidVector>("attackers")->Reset();
                beast->CastSpell(beast, 5185, false);
                if (!check(beast->IsNonMeleeSpellCasted(true) && active("bash on enemy healer") &&
                    action("bash on enemy healer")->GetTarget() == beast && cast("bash on enemy healer"), "secondary Bash chain")) return;
                _next = _elapsed + 1000;
                break;
            case 8:
                if (!check(beast->HasAura(5211, bot->GetGUID()) && !beast->IsNonMeleeSpellCasted(true), "secondary native stun")) return;
                beast->CombatStop(true); human->CombatStop(true); bot->CombatStop(true);
                ctx->GetValue<Unit*>("current target")->Set(nullptr);
                ctx->GetValue<GuidVector>("prioritized targets")->Set({});
                for (auto* p : players) p->SetHealth(p->GetMaxHealth());
                healReset();
                if (!check(!active("nature's swiftness") && !active("group heal setting") && !active("medium group heal setting"), "healthy party")) return;
                // Native trigger thresholds, group membership and actual spell effects are under test.
                for (size_t i = 1; i <= 3; ++i) players[i]->SetHealth(players[i]->CountPctFromMaxHealth(50));
                healReset();
                TC_LOG_INFO("playerbots", "Control fixture group nearby={} almost_full={} medium={} leader_phase={}",
                    ai->GetNearGroupMemberCount(), ctx->GetValue<uint8>("aoe heal", "almost full")->Get(),
                    ctx->GetValue<uint8>("aoe heal", "medium")->Get(), bot->GetPhaseMask());
                for (auto* p : players)
                    TC_LOG_INFO("playerbots", "Control fixture member={} map={} phase={} health={} distance={} assist={} los={}",
                        p->GetGUID().GetCounter(), p->GetMapId(), p->GetPhaseMask(), p->GetHealthPct(),
                        bot->GetDistance(p), bot->IsValidAssistTarget(p), bot->IsWithinLOSInMap(p));
                if (!check(active("group heal setting") && active("medium group heal setting"), "three wounded in five")) return;
                if (bot->GetGlobalCooldownMgr().HasGlobalCooldown(sSpellMgr->GetSpellInfo(774)))
                {
                    if (!check(!_groupGcdObserved && !action("rejuvenation on not full")->isPossible(),
                        "native post-Bash GCD guard")) return;
                    _groupGcdObserved = true;
                    TC_LOG_INFO("playerbots", "Control fixture native GCD blocks Rejuvenation; waiting without clearing it");
                    _next = _elapsed + 2000;
                    return;
                }
                if (!check(cast("rejuvenation on not full"), "group Rejuvenation")) return;
                break;
            case 9:
            {
                uint32 auras = 0;
                for (auto* p : players) if (p->HasAura(774, bot->GetGUID())) ++auras;
                if (!check(auras == 1, "native party Rejuvenation aura")) return;
                for (auto* p : players) { p->RemoveAurasDueToSpell(774, bot->GetGUID()); p->SetHealth(p->GetMaxHealth()); }
                bot->SetHealth(bot->CountPctFromMaxHealth(5));
                healReset();
                if (!check(!ai->HasStrategy("heal", BOT_STATE_COMBAT) && !active("nature's swiftness"),
                    "caster strategy must not spend emergency-heal buff")) return;
                _originalStrategies.clear();
                for (auto const& name : ai->GetStrategies(BOT_STATE_COMBAT)) _originalStrategies += "+" + name + ",";
                _strategyChanged = true;
                ai->ChangeStrategy("+heal", BOT_STATE_COMBAT);
                if (!check(active("nature's swiftness") && cast("nature's swiftness"), "emergency Swift chain")) return;
                _next = _elapsed + 200;
                break;
            }
            case 10:
                if (!check(bot->HasAura(132158), "native Swift buff")) return;
                if (!check(cast("healing touch"), "Swift Healing Touch")) return;
                _next = _elapsed + 200;
                break;
            case 11:
                if (!check(!bot->HasAura(132158) && !bot->IsNonMeleeSpellCasted(true) && bot->GetHealthPct() > 10,
                    "native instant heal and buff consumption")) return;
                TC_LOG_INFO("playerbots", "Control fixture healing group_triggers=true rejuvenation=774 swiftness=consumed instant=true health_pct={}", bot->GetHealthPct());
                // Let the native Healing Touch GCD expire before the next channel.
                _next = _elapsed + 2500;
                break;
            case 12:
                for (auto* p : players) p->SetHealth(p->CountPctFromMaxHealth(25));
                healReset();
                if (!check(active("medium group heal setting") && cast("tranquility"), "medium group Tranquility")) return;
                _next = _elapsed + 3000;
                break;
            case 13:
            {
                Spell* channel = bot->GetCurrentSpell(CURRENT_CHANNELED_SPELL);
                uint32 healed = 0;
                for (auto* p : players)
                    if (p->HasAura(44203, bot->GetGUID()) && p->GetHealthPct() > 25) ++healed;
                if (!check(channel && channel->GetSpellInfo()->Id == 740 && healed >= 3,
                    "native Tranquility channel, periodic aura and health increase")) return;
                TC_LOG_INFO("playerbots", "Control fixture tranquility channel=740 periodic_aura=44203 healed={}", healed);
                Finish(true, "native control, secondary caster, shapeshift, group healing and Swift effects");
                return;
            }
        }
        TC_LOG_INFO("playerbots", "Control fixture phase={} passed=true", _phase);
        ++_phase;
    }
};
DruidControlTest* Test = nullptr;
}
bool HandleDruidControlTest(ChatHandler* handler, std::string const& operation)
{
    if (handler->GetSession() || !Test || !sPlayerbotAIConfig->enabled) return false;
    std::istringstream input(sConfigMgr->GetStringDefault("AiPlayerbot.DruidControlTestGuids", ""));
    std::vector<ObjectGuid> guids;
    uint32 low;
    while (input >> low)
    {
        auto guid = ObjectGuid::Create<HighGuid::Player>(low);
        if (!low || std::find(guids.begin(), guids.end(), guid) != guids.end() ||
            !sPlayerbotAIConfig->IsInRandomAccountList(sCharacterCache->GetCharacterAccountIdByGuid(guid))) return false;
        guids.push_back(guid);
    }
    if (guids.size() != 5 || !input.eof()) return false;
    if (operation == "start") return Test->Start(guids);
    if (operation == "cleanup") { Test->Finish(false, "console cleanup"); return true; }
    return false;
}
void AddDruidControlTest() { Test = new DruidControlTest(); }
