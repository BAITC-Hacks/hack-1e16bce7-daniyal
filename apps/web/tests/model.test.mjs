import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validate, parseHistory, levelsFor, recommend, enroll, finish, importDataset, applyEffects, availability, targetFor, coverage } from '../src/app/career/model.ts';
const fixture = name => readFileSync(new URL('../public/demo-data/' + name, import.meta.url), 'utf8').replace(/^\uFEFF/, '');
const people = JSON.parse(fixture('employees.json')), events = JSON.parse(fixture('events.json')), skills = JSON.parse(fixture('skills.json'));
const data = { meta: people.meta, employees: people.employees, events: events.events, skills: skills.skills, role_profiles: skills.role_profiles, history: parseHistory(fixture('activity_history.csv')) };
const jsonFile = (name, value) => ({ name, size: 100, text: async () => JSON.stringify(value) });

test('provided dataset validates and all 200 profiles can be evaluated', () => {
  validate(data); assert.equal(data.employees.length, 200); assert.equal(data.history.length, 2743);
  for (const person of data.employees) {
    const results = recommend(data, person);
    assert.ok(results.length <= 3);
    assert.ok(coverage(levelsFor(data, person), targetFor(data, person)) >= 0);
    for (const result of results) { assert.equal(result.event.mandatory, false); assert.equal(availability(data, person, result.event), null); assert.ok(result.gains.some(g => g.target > g.before)); }
  }
});
test('review snapshot replays only subsequent completions without modifying imported levels', () => {
  const p = data.employees[0], local = structuredClone(data);
  local.history = [{ record_id:'test', employee_id:p.employee_id, event_id:'EV_005', date:local.meta.as_of_date, due_date:'', status:'completed', completion_pct:100, score:null, feedback_rating:null, assigned_by:'self' }];
  const expected = applyEffects(p.skills, local.events.find(e => e.event_id === 'EV_005'));
  assert.deepEqual(levelsFor(local, p), expected); assert.deepEqual(levelsFor(local, p), expected); assert.deepEqual(local.employees[0].skills, p.skills);
  local.history[0].date = p.last_review_date;
  assert.deepEqual(levelsFor(local, p), p.skills);
});
test('completion updates derived levels once, removes recommendation, and cancellation gives no gain', () => {
  const p = data.employees[0], chosen = recommend(data, p)[0]; assert.ok(chosen);
  const enrolled = enroll(data, p.employee_id, chosen.event.event_id), record = enrolled.history.at(-1);
  assert.throws(() => enroll(enrolled, p.employee_id, chosen.event.event_id), /Уже в плане/);
  const canceled = finish(enrolled, record.record_id, 'declined'); assert.deepEqual(levelsFor(canceled, p), levelsFor(data, p));
  const done = finish(enrolled, record.record_id, 'completed'); validate(done);
  assert.deepEqual(levelsFor(done, p), applyEffects(levelsFor(data, p), chosen.event));
  assert.throws(() => finish(done, record.record_id, 'completed'), /уже обработана/);
  assert.ok(!recommend(done, p).some(r => r.event.event_id === chosen.event.event_id));
});
test('gains respect event cap and never decrease existing levels', () => {
  const event = { develops_skills: [{skill_id:'A',gain:1,max_level:3}, {skill_id:'B',gain:2,max_level:5}] };
  assert.deepEqual(applyEffects({A:5,B:4}, event), {A:5,B:5});
});
test('judge profile import merges new people and rejects invalid batches atomically', async () => {
  const judge = {...structuredClone(data.employees[0]), employee_id:'JUDGE_1'};
  const imported = await importDataset(data, [jsonFile('profiles.json',{employees:[judge]})], 'merge');
  assert.equal(imported.employees.length,201); assert.equal(data.employees.length,200);
  judge.skills.SK_PYTHON = 7;
  await assert.rejects(importDataset(data,[jsonFile('employees.json',{employees:[judge]})],'merge'), /Некорректный профиль/);
  assert.equal(data.employees.length,200);
});
test('reject malformed CSV, foreign keys and out-of-range skill data', () => {
  assert.throws(() => parseHistory('record_id,employee_id\na,b'), /10 столбцов/);
  assert.throws(() => parseHistory('"unclosed'), /кавычка/);
  const invalid = structuredClone(data); invalid.history[0].event_id = 'UNKNOWN'; assert.throws(() => validate(invalid), /строка истории/);
});
test('critical career skill outranks smallest irrelevant skill and related refusals reduce priority', () => {
  const local = structuredClone(data), p = local.employees.find(p => p.role === 'Backend Engineer' && p.grade === 'Middle');
  local.history = []; p.skills.SK_SYSTEM_DESIGN=2; p.skills.SK_API_DESIGN=2; p.skills.SK_PUBLIC_SPEAKING=0;
  const before = recommend(local,p), speaking = local.events.find(e=>e.event_id==='EV_036');
  assert.notEqual(before[0].event.event_id, speaking.event_id);
  for(let i=0;i<3;i++) local.history.push({record_id:'skip'+i,employee_id:p.employee_id,event_id:speaking.event_id,date:'2026-09-20',due_date:'',status:'no_show',completion_pct:0,score:null,feedback_rating:null,assigned_by:'self'});
  assert.notEqual(recommend(local,p)[0].event.event_id,speaking.event_id);
});
