#!/usr/bin/env python3
"""Exercise native BotFactory pet registration and persistence under ASan/UBSan.

Compiles InitPet, Player slot/current-pet methods, LoadPetList and SavePetToDB.
World creation, spell effects and database execution are bounded doubles. The
database records the real generated pet SQL and transaction membership; this
does not replace a live MySQL/relogin/Call Pet test or repair old slot-255 rows.
Policy source: NotCronky 969150c0d398039e993a88913fe71a528b74dc41 and our
Spell::EffectTameCreature. --verify-mutations proves the repaired paths fail.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
compiler = sys.argv[2]


def block(text, signature):
    start = text.index(signature)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


factory = block((root / "modules/mod_playerbots/src/Factory/BotFactory.cpp").read_text(),
                "void BotFactory::InitPet()")
player_source = (root / "src/server/game/Entities/Player/Player.cpp").read_text()
player_methods = "\n".join(block(player_source, signature) for signature in (
    "void Player::SetCurrentPetId(", "void Player::AddNewPet(",
    "uint32 Player::GetPetIdBySlot(", "int8 Player::GetSlotByPetId(",
    "int8 Player::GetSlotForNewPet(", "void Player::LoadPetList()"))
save_pet = block((root / "src/server/game/Entities/Pet/Pet.cpp").read_text(), "void Pet::SavePetToDB(")
slots = block((root / "src/server/game/Entities/Pet/PetDefines.h").read_text(), "enum PetSlot") + ";"

prefix = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdio>
#include <cstdint>
#include <ctime>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
using uint8 = std::uint8_t;
using int8 = std::int8_t;
using uint32 = std::uint32_t;
#define ASSERT(x) assert(x)
int errors = 0;
#define TC_LOG_ERROR(...) (++errors)
constexpr uint32 CLASS_HUNTER = 3, CLASS_WARLOCK = 9, POWER_MANA = 0, HUNTER_PET = 1;
constexpr uint32 UNIT_FIELD_LEVEL = 1, UNIT_FIELD_PET_EXPERIENCE = 2,
    UNIT_FIELD_BYTES_2 = 3, UNIT_CAN_BE_RENAMED = 4, UNIT_FIELD_CREATED_BY_SPELL = 5;
constexpr uint32 ACTION_BAR_INDEX_START = 0, ACTION_BAR_INDEX_END = 10, PETSPELL_REMOVED = 2;
enum Statements { CHAR_INS_CURRENT_PET_ID, CHAR_DEL_CURRENT_PET_ID,
    CHAR_UPD_CHAR_PET_SLOT_BY_ID, CHAR_SEL_PET_SLOT_LIST };
struct CharacterDatabasePreparedStatement {
    Statements id;
    std::array<uint32, 3> values{};
    void setUInt32(int index, uint32 value) { values[index] = value; }
    void setUInt8(int index, uint8 value) { values[index] = value; }
};
struct Operation {
    std::shared_ptr<CharacterDatabasePreparedStatement> statement;
    std::string sql;
};
struct Transaction {
    std::vector<Operation> operations;
    void Append(CharacterDatabasePreparedStatement* stmt) { operations.push_back({std::shared_ptr<CharacterDatabasePreparedStatement>(stmt), {}}); }
    void Append(char const* sql) { operations.push_back({nullptr, sql}); }
};
using CharacterDatabaseTransaction = std::shared_ptr<Transaction>;
struct Field {
    uint32 number = 0;
    std::string text;
    uint32 GetUInt32() const { return number; }
    uint8 GetUInt8() const { return number; }
    std::string GetString() const { return text; }
};
struct QueryResult {
    std::vector<std::array<Field, 4>> rows;
    size_t row = 0;
    Field* Fetch() { return rows[row].data(); }
    bool NextRow() { return ++row < rows.size(); }
};
using PreparedQueryResult = std::shared_ptr<QueryResult>;
struct PetRow { uint32 id, entry, owner, level, slot; };
struct Database {
    std::map<uint32, PetRow> pets;
    std::map<uint32, uint32> current;
    std::vector<uint32> insertedSlots;
    std::vector<size_t> transactionSizes;
    uint32 begins = 0, commits = 0, directWrites = 0;
    CharacterDatabasePreparedStatement* GetPreparedStatement(Statements id) {
        return new CharacterDatabasePreparedStatement{id};
    }
    CharacterDatabaseTransaction BeginTransaction() {
        ++begins;
        return std::make_shared<Transaction>();
    }
    void apply(CharacterDatabasePreparedStatement const& stmt) {
        auto const& v = stmt.values;
        switch (stmt.id) {
            case CHAR_INS_CURRENT_PET_ID: current[v[0]] = v[1]; break;
            case CHAR_DEL_CURRENT_PET_ID: current.erase(v[0]); break;
            case CHAR_UPD_CHAR_PET_SLOT_BY_ID:
                assert(pets.count(v[2]) && pets.at(v[2]).owner == v[1]);
                pets.at(v[2]).slot = v[0];
                break;
            default: assert(false);
        }
    }
    void CommitTransaction(CharacterDatabaseTransaction trans) {
        ++commits;
        transactionSizes.push_back(trans->operations.size());
        for (auto const& op : trans->operations) {
            if (op.statement) apply(*op.statement);
            else if (op.sql.starts_with("REPLACE INTO character_pet (")) {
                PetRow row{};
                unsigned model, exp, react;
                auto offset = op.sql.find("VALUES (");
                assert(offset != std::string::npos);
                assert(std::sscanf(op.sql.c_str() + offset, "VALUES (%u,%u,%u,%u,%u,%u,%u,%u",
                    &row.id, &row.entry, &row.owner, &model, &row.level, &exp, &react, &row.slot) == 8);
                pets[row.id] = row;
                insertedSlots.push_back(row.slot);
            }
            else assert(op.sql == "auras" || op.sql == "spells" || op.sql == "history");
        }
    }
    void Execute(CharacterDatabasePreparedStatement* raw) {
        std::unique_ptr<CharacterDatabasePreparedStatement> stmt(raw);
        ++directWrites;
        apply(*stmt);
    }
    void EscapeString(std::string&) {}
    PreparedQueryResult Query(CharacterDatabasePreparedStatement* raw) {
        std::unique_ptr<CharacterDatabasePreparedStatement> stmt(raw);
        assert(stmt->id == CHAR_SEL_PET_SLOT_LIST);
        auto result = std::make_shared<QueryResult>();
        for (auto const& [id, pet] : pets)
            if (pet.owner == stmt->values[0] && pet.slot >= stmt->values[1] && pet.slot <= stmt->values[2])
                result->rows.push_back({Field{pet.slot, {}}, Field{id, {}}, Field{pet.entry, {}}, Field{0, "pet"}});
        return result->rows.empty() ? nullptr : result;
    }
} CharacterDatabase;
struct Guid {
    uint32 value;
    uint32 GetCounter() const { return value; }
    bool IsPlayer() const { return true; }
};
struct SpellInfo {
    uint32 Id;
    bool passive = false;
    bool IsPassive() const { return passive; }
};
struct SpellManager {
    std::map<uint32, SpellInfo> spells{{1, {1, false}}, {2, {2, true}}, {3, {3, false}}};
    SpellInfo const* GetSpellInfo(uint32 id) { auto it = spells.find(id); return it == spells.end() ? nullptr : &it->second; }
} spellManager;
SpellManager* sSpellMgr = &spellManager;
struct CreatureTemplate {
    uint32 Entry = 42, minlevel = 1;
    std::string Name = "Wolf";
    bool tameable = true, exotic = false;
    bool IsTameable(bool canExotic) const { return tameable && (!exotic || canExotic); }
};
using CreatureTemplateContainer = std::map<uint32, CreatureTemplate>;
struct ObjectManager {
    CreatureTemplateContainer templates{{42, CreatureTemplate{}}};
    CreatureTemplateContainer const* GetCreatureTemplates() { return &templates; }
    CreatureTemplate const* GetCreatureTemplate(uint32 id) { return &templates.at(id); }
} objectManager;
ObjectManager* sObjectMgr = &objectManager;
uint32 urand(uint32 low, uint32 high) { assert(low <= high); return low; }
struct Pet;
struct Map {
    uint32 added = 0;
    void AddToMap(Pet*) { ++added; }
};
struct PetData { uint32 Entry = 0, PetNumber = 0; std::string Name; };
struct Player {
    uint32 playerClass = CLASS_HUNTER, level = 30, m_currentPetId = 0, createAttempts = 0, initialized = 0;
    bool exotic = false, failCreation = false;
    Guid guid{123};
    std::set<uint32> known{883, 83245};
    std::map<int8, PetData> m_petList;
    Map world;
    Map* map = &world;
    Pet* pet = nullptr;
    std::vector<std::unique_ptr<Pet>> owned;
    ~Player();
    Pet* GetPet() { return pet; }
    uint32 GetClass() { return playerClass; }
    uint32 GetLevel() { return level; }
    std::string GetName() { return "Hunter"; }
    Guid GetGUID() const { return guid; }
    Map* GetMap() { return map; }
    bool CanTameExoticPets() { return exotic; }
    bool HasSpell(uint32 id) const { return known.count(id); }
    Pet* CreateTamedPetFrom(uint32 entry, uint32);
    void SetMinion(Pet* value, bool) { pet = value; }
    void PetSpellInitialize() { ++initialized; }
    void SetCurrentPetId(uint32, CharacterDatabaseTransaction = nullptr);
    void AddNewPet(int8, Pet*);
    uint32 GetPetIdBySlot(uint8) const;
    int8 GetSlotByPetId(uint32) const;
    int8 GetSlotForNewPet() const;
    void LoadPetList();
};
struct ActionBarEntry {
    uint32 GetType() { return 0; }
    uint32 GetAction() { return 0; }
};
struct CharmInfo {
    uint32 number;
    ActionBarEntry entry;
    uint32 GetPetNumber() { return number; }
    ActionBarEntry* GetActionBarEntry(uint32) { return &entry; }
};
struct SpellHistory {
    template<class T> void SaveToDB(CharacterDatabaseTransaction trans) { trans->Append("history"); }
};
struct PetSpell { uint32 state; };
using PetSpellMap = std::map<uint32, PetSpell>;
struct Pet {
    Player* owner;
    uint32 entry, level = 1, health = 1, statRefreshes = 0;
    CharmInfo charm;
    CharmInfo* m_charmInfo = &charm;
    std::string m_name = "Wolf";
    PetSpellMap m_spells{{1, {0}}, {2, {0}}, {3, {PETSPELL_REMOVED}}, {4, {0}}};
    std::set<uint32> autocast;
    SpellHistory history;
    Pet(Player* owner, uint32 entry, uint32 id) : owner(owner), entry(entry), charm{id, {}} {}
    Player* GetOwner() { return owner; }
    Guid GetOwnerGUID() { return owner->GetGUID(); }
    uint32 GetEntry() { return entry; }
    bool isControlled() { return true; }
    bool IsTemporary() { return false; }
    Map* GetMap() { return owner->GetMap(); }
    Pet* ToCreature() { return this; }
    CharmInfo* GetCharmInfo() { return m_charmInfo; }
    std::string GetName() { return m_name; }
    void SetUInt32Value(uint32 field, uint32 value) { if (field == UNIT_FIELD_LEVEL) level = value; }
    uint32 GetUInt32Value(uint32) { return 0; }
    uint32 GetLevel() { return level; }
    void SetLevel(uint32 value) { level = value; }
    void InitStatsForLevel(uint32) { ++statRefreshes; }
    void InitTalentForLevel() {}
    uint32 GetHealth() { return health; }
    uint32 GetMaxHealth() { return 1000; }
    void SetHealth(uint32 value) { health = value; }
    uint32 GetPower(uint32) { return 0; }
    uint32 GetNativeDisplayId() { return 1; }
    uint32 GetReactState() { return 0; }
    uint32 getPetType() { return HUNTER_PET; }
    uint32 GetSpecializationId() { return 0; }
    bool HasByteFlag(uint32, uint32, uint32) { return false; }
    void _SaveAuras(CharacterDatabaseTransaction trans) { trans->Append("auras"); }
    void _SaveSpells(CharacterDatabaseTransaction trans) { trans->Append("spells"); }
    SpellHistory* GetSpellHistory() { return &history; }
    void ToggleAutocast(SpellInfo const* spell, bool) { autocast.insert(spell->Id); }
    void SavePetToDB(CharacterDatabaseTransaction = nullptr);
};
Player::~Player() = default;
Pet* Player::CreateTamedPetFrom(uint32 entry, uint32) {
    ++createAttempts;
    if (failCreation) return nullptr;
    owned.push_back(std::make_unique<Pet>(this, entry, 900 + owned.size()));
    return owned.back().get();
}
struct BotFactory {
    Player* bot;
    void InitPet();
};
'''

tests = r'''
void reset() { CharacterDatabase = {}; objectManager = {}; errors = 0; }
void checkCreationAndReload() {
    reset();
    Player bot;
    BotFactory factory{&bot};
    factory.InitPet();
    assert(bot.pet && bot.createAttempts == 1);
    auto petId = bot.pet->GetCharmInfo()->GetPetNumber();
    assert(bot.GetPetIdBySlot(PET_SLOT_ACTIVE_FIRST) == petId && "new pet must be registered before saving");
    assert(bot.m_currentPetId == petId && "new pet must become the current pet");
    assert(CharacterDatabase.begins == 1 && CharacterDatabase.commits == 1 &&
           CharacterDatabase.directWrites == 0 && "pet and current ID must share one transaction");
    assert(CharacterDatabase.current.at(bot.guid.value) == petId);
    assert(CharacterDatabase.insertedSlots == std::vector<uint32>{0} && "pet SQL must contain the registered slot");
    assert(CharacterDatabase.pets.at(petId).slot == PET_SLOT_ACTIVE_FIRST);
    assert(bot.world.added == 1 && bot.initialized == 1 && errors == 0);
    assert(bot.pet->GetLevel() == bot.level && bot.pet->health == 1000);
    assert(bot.pet->autocast == std::set<uint32>{1}); // No passive, removed or unknown spells.
    factory.InitPet();
    assert(bot.createAttempts == 1 && CharacterDatabase.commits == 1 && bot.pet->statRefreshes == 2);
    // Dismissed/temporarily unsummoned pet: empty live pointer is not an empty roster.
    bot.pet = nullptr;
    factory.InitPet();
    assert(bot.createAttempts == 1 && CharacterDatabase.pets.size() == 1 && "refresh must preserve a dismissed pet");
    // Recreate the player and use the native roster loader against committed rows.
    Player reloaded;
    reloaded.LoadPetList();
    assert(reloaded.GetPetIdBySlot(PET_SLOT_ACTIVE_FIRST) == petId && "registered pet must survive roster reload");
    BotFactory{&reloaded}.InitPet();
    assert(reloaded.createAttempts == 0 && CharacterDatabase.pets.size() == 1);
}
void checkGuardsAndExistingPets() {
    reset();
    Player bot;
    bot.m_petList[PET_SLOT_ACTIVE_FIRST] = {42, 777, "Existing"};
    BotFactory{&bot}.InitPet();
    assert(bot.createAttempts == 0 && bot.m_petList.size() == 1 && CharacterDatabase.commits == 0);
    bot.m_petList.clear();
    bot.known.clear();
    BotFactory{&bot}.InitPet();
    assert(bot.createAttempts == 0 && CharacterDatabase.commits == 0 && errors == 1);
    bot.known.insert(883);
    // Stable-only pets do not replace the active slot used by Call Pet 1.
    bot.m_petList[PET_SLOT_STABLE_FIRST] = {42, 778, "Stabled"};
    BotFactory{&bot}.InitPet();
    assert(bot.m_petList.at(PET_SLOT_STABLE_FIRST).PetNumber == 778);
    assert(bot.GetPetIdBySlot(PET_SLOT_ACTIVE_FIRST) != 0);
    reset();
    Player otherClass;
    otherClass.playerClass = CLASS_WARLOCK;
    BotFactory{&otherClass}.InitPet();
    assert(otherClass.createAttempts == 0 && CharacterDatabase.commits == 0);
    otherClass.pet = otherClass.CreateTamedPetFrom(42, 0); // Existing summoned minion double.
    BotFactory{&otherClass}.InitPet();
    assert(otherClass.pet->statRefreshes == 1 && otherClass.pet->autocast == std::set<uint32>{1});
    assert(otherClass.m_petList.empty() && CharacterDatabase.commits == 0);
}
void checkFailurePaths() {
    reset();
    Player bot;
    bot.map = nullptr;
    BotFactory{&bot}.InitPet();
    assert(bot.createAttempts == 0 && errors == 0);
    bot.map = &bot.world;
    for (uint32 failure : {0, 1, 2, 3, 4}) {
        reset();
        auto& creature = objectManager.templates.at(42);
        if (failure == 0) creature.tameable = false;
        if (failure == 1) creature.minlevel = bot.level + 1;
        if (failure == 2) creature.exotic = true;
        if (failure == 3) creature.Name = std::string(22, 'x');
        if (failure == 4) bot.failCreation = true;
        BotFactory{&bot}.InitPet();
        assert(!bot.pet && bot.m_petList.empty() && bot.m_currentPetId == 0);
        assert(CharacterDatabase.begins == 0 && CharacterDatabase.pets.empty() && errors == 1);
    }
}
int main() {
    checkCreationAndReload();
    checkGuardsAndExistingPets();
    checkFailurePaths();
    std::cout << "PASS: Hunter pet registration, atomic save, roster reload and repeated initialization\n";
}
'''


def replace_once(source, old, new):
    assert source.count(old) == 1, f"Mutation anchor changed: {old}"
    return source.replace(old, new, 1)


environment = dict(os.environ, ASAN_OPTIONS="halt_on_error=1:detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1")
with tempfile.TemporaryDirectory(prefix="loa-hunter-pet-") as directory:
    def run(name, body=factory, expected_assertion=None):
        binary = Path(directory) / name
        source = prefix + slots + player_methods + save_pet + body + tests
        subprocess.run([compiler, "-x", "c++", "-std=c++20", "-g", "-O1",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-", "-o", str(binary)],
                       input=source, text=True, check=True)
        result = subprocess.run([str(binary)], env=environment, capture_output=True, text=True)
        if expected_assertion:
            assert (result.returncode != 0 and "Assertion" in result.stderr
                    and expected_assertion in result.stderr), result.stderr or f"Mutation survived: {name}"
            print(f"Mutation {name}: rejected by '{expected_assertion}'", flush=True)
        elif result.returncode:
            sys.stderr.write(result.stderr)
            raise subprocess.CalledProcessError(result.returncode, [str(binary)])
        else:
            print(result.stdout, end="", flush=True)

    run("current")
    if "--verify-mutations" in sys.argv[3:]:
        run("missing-registration", replace_once(factory, "bot->AddNewPet(newPetSlot, pet);", ""),
            "new pet must be registered before saving")
        run("missing-current-pet", replace_once(factory,
            "bot->SetCurrentPetId(pet->GetCharmInfo()->GetPetNumber(), trans);", ""),
            "new pet must become the current pet")
        run("separate-current-write", replace_once(factory,
            "bot->SetCurrentPetId(pet->GetCharmInfo()->GetPetNumber(), trans);",
            "bot->SetCurrentPetId(pet->GetCharmInfo()->GetPetNumber());"),
            "pet and current ID must share one transaction")
        run("separate-pet-save", replace_once(factory, "pet->SavePetToDB(trans);", "pet->SavePetToDB();"),
            "pet and current ID must share one transaction")
        run("duplicate-dismissed-pet", replace_once(factory,
            "if (bot->GetPetIdBySlot(PET_SLOT_ACTIVE_FIRST))", "if (false)"),
            "refresh must preserve a dismissed pet")
        late_registration = replace_once(factory, "bot->AddNewPet(newPetSlot, pet);", "")
        late_registration = replace_once(late_registration, "pet->SavePetToDB(trans);",
                                          "pet->SavePetToDB(trans); bot->AddNewPet(newPetSlot, pet);")
        run("registration-after-save", late_registration, "pet SQL must contain the registered slot")
