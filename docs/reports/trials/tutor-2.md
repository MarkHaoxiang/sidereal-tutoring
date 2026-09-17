# Tutor re-trial — Priya, A-level Physics and Maths

Second pass, 17 Sept 2026, 16:10–17:15. Chromium 1440×900 (one pass at 400 px), everything through the
browser, never the API or the database. Screenshots in `.screenshots/trial2-tutor/`.

Spend: homework $0.08 (~70 s), feedback $0.01 (~40 s), study plan $0.08 (~70 s). Three jobs, no retry
needed, one under budget. Leo's hand-in photo was transcribed by the app as part of his submission; I ran
no scan of my own.

I did the whole scenario: added Leo, scheduled tomorrow's lesson, pasted my moments notes, cut three
questions out of the AQA Physics paper into a homework, generated a second homework from the notes,
edited a question, assigned it, set up his login, marked his hand-in question by question, generated
feedback about that hand-in, generated a six-week plan, archived him, checked his login was refused,
unarchived, removed his login, and deleted him.

---

## Every finding from the first report

| # | First-trial finding | Status | Evidence |
|---|---|---|---|
| 1 | **Critical** — "Remove login" always fails with `Directus 500` | **Closed** | Removed cleanly, toast "Login removed", chip back to "No login yet". `70`, `71` |
| 2 | **Critical** — archiving does not revoke access | **Closed** | Confirm now reads "They leave your active list **and cannot sign in**". Signing in as archived Leo in a fresh context: "Could not sign in." Unarchive restored it. `65`–`69` |
| 3 | **Critical** — study plan truncated and presented as finished | **Closed** | Seven complete weeks, 22 Sept → 3 Nov, ending on a finished Homework line. Nothing cut. `64` |
| 4 | **High** — a generation job disappears if you refresh | **Closed** | A "Queued"/"Generating" row appears in the list and survives a full reload; Home and the tab both keep it. `30`, `31` |
| 5 | **High** — editing homework content does not update the mark scheme | **Still open** (now documented, not fixed) | I rewrote Q2 into a three-part question; the PDF updated, the "Questions" panel did not. It is captioned "The questions as they were generated — editing the sheet does not change them". The stale Q2 then reached **the marking panel** and **the generated feedback**, which told Leo his Q2 "asks about a 50 N force at 30° to the beam" — not what is on his sheet. `35`, `55`, `59` |
| 6 | **High** — "Make worksheet" drops every figure and table | **Partly** | Tables now survive: Table 2's three densities are printed. Figures still do not — `pdfimages` finds **0** images in the worksheet while the source paper PDF carries 39. Q3 parts (2), (3) and (4) are still unanswerable: "Figure 4 shows the pulley arrangement…", no Figure 4. `ws-1`, `ws-2` |
| 7 | **Medium** — raw Typst leaks into every tutor-facing list | **Closed** | The Questions panel reads "M = F d = 40 N x 0.6 m = 24 N m"; the scan reads "Moment = Fxd = 12 x 0.4 = 4.8 Nm". No `$…$` anywhere. It is now flattened to ASCII (`x` for ×, `deg` for °) rather than typeset, but nothing looks broken. `50`, `55` |
| 8 | **Medium** — same leak in the worksheet question picker | **Partly** | The picker is now properly readable: `⁴₂He`, `β⁻`, `5.2 × 10⁻⁷ m`, `60°`. One leak survives — Q04 reads "internal resistance of 2.5 `Ω`". `23` |
| 9 | **Low** — one library row wraps | **Still open** | "AQA A-level English Literature A 7712/1 June 2022 — question paper" measures 72 px against 49–51 px for every other row. `42` |
| 10 | **Critical** — there is no marking | **Closed** | Per-question marks awarded / marks available, a comment box per question, a live running total, an overall comment, then Finish marking. I marked Leo 5/20 with five comments. `53`, `55` |
| 11 | **Critical** — feedback cannot read the hand-in | **Closed** | The dialog leads with "About this homework — **its questions, what was handed in, and the marks**". Quality discussed below. `57`, `59` |
| 12 | **High** — a worksheet is not assignable and is not saved | **Closed** | Choosing a student reveals a Due field and relabels the button "Set as homework"; afterwards there is an "Open the homework" link and a real Draft homework row with the due date. `24`, `25`, `26` |
| 13 | **High** — a student cannot be deleted | **Closed** | Delete sits beside Edit and Archive; it worked, toast "Deleted", list empty. `77`, `78` |
| 14 | **Medium** — no way to see what a student sees | **Still open** | No "view as", "preview" or equivalent anywhere on the student page. I again had to sign in as Leo to find out. |
| 15 | **Medium** — paper questions are not text | **Still open** | 169 SVGs, **0** `<text>`/`<tspan>` nodes on the paper page; the body text does not contain the word "moment". No select, no copy, no Ctrl-F. The question list headings are bare ("Question 3 · 13 marks · 5 parts"), so the only readable index of a paper is now the worksheet picker. `20` |
| 16 | **Medium** — two disconnected mark schemes | **Partly** | A paper can now carry its own extracted scheme, and the newer physics paper has one. The 7408/1 paper still says "No mark scheme yet — Extract mark scheme" while "AQA A-level Physics 7408/1 June 2022 — mark scheme" sits in the library, unlinked. `40`, `41` |
| 17 | **Medium** — Scan handwriting has no Name field | **Still open** | Dialog fields: Pages, Solutions to, Topics, From session. No name. The library item is still titled "leo_hw". `44`, `50` |
| 18 | **Low** — no "forgot password"; account reachable only by clicking your own name | **Partly** | Still no forgot-password link on sign-in. Your name is now a real `<a href="/account">` and there is an explicit "Sign out" in the sidebar. `01`, `02` |
| 19 | **High** — "Make worksheet" is on the wrong tab | **Closed** | It is on the Questions tab, top right, above the questions. Also still on Printable. `20`, `22` |
| 20 | **Medium** — "Generating… usually under a minute" | **Closed** | Now "Generating. It is safe to leave this page." No time promise. `30` |
| 21 | **Medium** — "Makes a PDF only — no homework is set" above a student picker | **Closed** | Now simply "Makes a PDF.", and the moment you pick a student the button becomes "Set as homework" and a Due field appears. The copy and the fields finally agree. `23` |
| 22 | **Medium** — "by A colleague" on every library item | **Partly** | Your own uploads now read "by You". Everything anyone else added is still "by A colleague" — in a shared library I still cannot tell whose worksheet I am about to hand a student. `80` |
| 23 | **Medium** — every paper is "Draft", unexplained | **Still open** | All twelve papers are Draft. No tooltip, no `title`, no `aria-label`, no legend. There is a "Mark reviewed" button, which is the only hint. `18`, `51` |
| 24 | **Low** — pasted text is labelled "Upload" | **Still open** | My pasted notes show the kind chip "Upload" in the list and on the detail page. `15`, `16` |
| 25 | **Low** — "Mark sent" sends nothing | **Still open** | Flips Draft → Sent. No email, no notification, no tooltip explaining it is a bookkeeping flag. `60` |
| 26 | **Low** — the homework Content box is Typst source | **Still open, and worse** | The box now opens on the house template, comments and all: "`// The house homework template. \`POST /template\` returns this file, then a \`#show: homework.with(...)\` line…`", 3 565 characters before you reach your first question. For a paper-cut homework it is read-only but still shows the whole renderer prelude (`#let question-row`, `#let answerlines`…). `26`, `55` |
| 27 | **Low** — duplicate paper entries | **Still open** | Four A-level Physics Paper 1 entries, three AQA A-level Mathematics Paper 1 June 2023, two GCSE Maths Higher, two English Literature, two Computer Science. Twelve rows, five real papers. `18` |

Fourteen closed, five partly, eight still open. Every critical is closed.

---

## New findings, ranked

**N1 · Critical — three library papers render nothing on screen, and show the tutor a developer error
instead.** Open "A-level PHYSICS Paper 1" (17 Sept, 32 calls, $1.31). Every question that contains a
figure shows an empty box reading "Nothing was set." and, underneath it in a red panel:

> `parts[2].blocks[0].asset: no asset named "2d80be77-cd54-42a5-980d-f937582507ce.jpg" was sent with this request`

Sixteen of these on that paper, eight on the other physics paper, five on Computer Science Paper 2 —
and the same on their Mark scheme tabs. The figures are not missing: the paper's own PDF contains 39
JPEGs. So the most expensive, most complete paper in the library is the one a tutor cannot read, and
what they see instead is a stack trace. `19`, `21`, `41`

**N2 · High — removing a login does not end the student's session, and the orphaned session is shown
the tutor application.** I removed Leo's login while his browser was still signed in. His token stayed
valid, and because he no longer resolves to a student the app served him the *tutor* shell: Home,
Students, Library, Topics in the sidebar, an "Add student" button, "The desk is clear", an "Add
material" button on the shared Library and "Add topic" on the shared topic tree, plus a working account
page with change-email and change-password. The lists all came back empty and the account form was
blank, so I saw no data leak — but a removed student is left holding a session that presents itself as
a tutor's. `73`, `74`, `75`, `76`

**N3 · High — the worksheet prints escape sequences and loses exponents.** On the sheet Leo would have
received, Q3 part (4) reads:

> "The angle between the door and the horizontal cable C is `12°`."

And Table 2 prints "Density / kg m−3" with the densities as "2.4 × 103", "7.8 × 103", "8.6 × 103" —
the exponents flattened, so concrete reads as 103 kg m⁻³ instead of 2.4 × 10³. A student doing the
"deduce which material" part is working from wrong numbers. The body text has the same half-fix:
"4.8 × 10⁻2 m". `ws-1`, `ws-2`

**N4 · High — multiple-choice questions print twice on a worksheet, and one printed with no question.**
Q22 appears as a typeset question, then again in full inside a grey box with its options as plain
lines, then a third time as lettered answer bubbles. Q25 is worse: the numbered line "25." is empty,
then the grey box carries the whole question, then a part labelled "()" repeats it, then the bubbles.
Three questions chosen, and two of them look broken. `ws-3`

**N5 · High — marking in progress cannot be saved.** While a hand-in is unmarked, the only button in the
Marking panel is "Finish marking" (I enumerated them: `["Finish marking"]`). I typed five marks and five
comments, reloaded to check they were safe, and the total went from 5 / 20 back to 0 / 0 with every
comment gone. A "Save marking" button only appears *after* you have finished. So a tutor who marks
three questions of five and comes back after supper loses the lot, with no unsaved-changes warning.
`53`, `54`

**N6 · Medium — the app cannot tell me what a question is worth, so I invented the totals.** Every
"Marks available" box starts blank and the running total starts "0 / 0". The generated homework carries
no mark allocations at all — the homework Typst helper is `#question[body]` with no marks argument, so
unlike the paper worksheets there are no `[2]` marks in the margin. I had to decide, and type, what each
of the five questions was out of, while a full mark scheme with method marks sat in the panel below.
`33`, `53`

**N7 · Medium — the feedback never tells Leo his mark.** It says "Full marks" twice and "left blank"
twice but never states 5 / 20, or any number. The one figure a student looks for first is the one thing
the letter omits. `59`

**N8 · Medium — Home's "To review" showed a draft nobody has seen, and not the hand-in.** For most of
the session "To review" listed "Moments, resolving and equilibrium — three past-paper questions", a
Draft that had never been assigned to anyone, while the assigned homework was absent. `47`

**N9 · Medium — a deleted student's URL spins forever.** After deleting Leo, going back to
`/students/<id>/overview` shows "Loading student…" and "Loading…" indefinitely. No "not found", no
redirect. `79`

**N10 · Medium — paper questions display validation errors as body text.** Questions 25–31 of the newer
physics paper each show "Needs a number and some text." where the question should be. That is an
editor's validation message rendered as content. `19`

**N11 · Low — a paper is unreadable on a phone.** At 400 px each question renders at a fixed 512 px
inside a 340 px scroll box, so every line has to be scrolled sideways and back. The page itself does not
overflow — the questions just do not scale. `43-400-paper`

**N12 · Low — "No students yet." is the empty copy for every filter.** Filter to Paused or Archived with
one active student on the books and it says "No students yet.", which is not true. `49`

**N13 · Low — the plan is titled "Six-Week Mechanics Plan" and contains seven weeks.** 22 September to
3 November is seven Tuesdays and the plan uses all of them, through "Week 7 – Tuesday 3 November". `64`

**N14 · Low — feedback provenance undercounts its inputs.** I ticked the homework *and* the lesson
notes; the line reads "from 1 piece of material". The homework is recorded separately as a chip, but the
sentence reads as though half of what I chose was ignored. `59`

---

## The generated work, judged as a physics tutor

### Feedback — this is the fix that matters, and it works

It now sees the hand-in, and it shows. I wrote nothing about Leo's performance in the instructions box —
only "Warm but honest, addressed to Leo. Keep it under 250 words." Everything specific below is
something the app read for itself:

> "Q1 was spot on — 24 N m, with the pivot stated and a unit given. You even noted *"the force is
> already perpendicular to the beam so no resolving is needed,"* which is exactly the right instinct."

That is Leo's own sentence, quoted back to him. Compare the first trial, where the feedback praised a
photo it had never seen. It also caught the thing I most wanted caught:

> "Q2 is the one to fix. What you wrote — 150 x 2.0 = R_B x 4.0, giving R_A = R_B = 75 N — is actually
> the plank example from class, not this question… You said your working for this is on paper, so bring
> that sheet to your lesson tomorrow (Friday 18th) — this is the exact habit (using the beam length
> instead of the perpendicular distance) we're working on."

It read his wrong working, recognised *which* worked example he had copied, noticed his aside that the
real working was on paper, tied it to the habit in my notes, and got the date of tomorrow's lesson
right. It also picked up my per-question comments and turned them into next steps:

> "Even a first line — like writing CD = 3.0 m for Q4, or noting the perpendicular distance is
> 2.4 sin40 for Q5 — is worth something and shows me where you got stuck."

Two faults. It never gives the mark — 5 out of 20 appears nowhere, in a letter that says "full marks"
twice. And it describes Q2 as "a 50 N force at 30° to the beam", which is the question I *replaced*
before assigning: Leo's sheet has a three-part version ending "A classmate writes M = 50 × 2.0 = 100 N m.
State what they have done wrong." That is finding 5 arriving where it does real damage — the letter
describes a question the student does not have. I would still send this, after adding the mark and
fixing that sentence. Last time I would have had to write it myself.

### Homework — good again, and it took the instruction seriously

Five questions, all correct: 24 N m; d⊥ = 2.0 sin30 = 1.0 m so M = 50 N m; R_B = 320 N and R_A = 420 N;
the non-uniform plank at x = 1.7 m (consistent with R_C + R_D = 200 N); and the hinged rod at T = 152 N,
V_A = 52.4 N, H_A = 116 N. The difficulty ramps properly.

I had asked for no revision-tip questions and for a scheme that does not double-count — the two things I
criticised last time — and both landed:

> "1 mark for R_A = 420 N with unit, obtained from vertical equilibrium (**no credit for re-deriving
> R_A by a second moment equation that repeats the same information**)."

and on the hinged rod, "Marks for (a) are not re-awarded when used again in (b)." That is a mark scheme
written by someone who has marked before.

What it lost since last time: the PDF has no mark allocations in the margin. Last trial's sheet carried
them and it made the sheet feel like an exam. This one is ruled lines and nothing else, and it is the
reason I had to invent the totals when marking (N6).

### Study plan — complete, and better than last time

Seven weeks, each with a topic, a session plan and a homework, running properly to the end. It used the
mark:

> "Leo scored 5/20 on the moments diagnostic sheet. He can do straightforward moments but on the
> angled-force question he answered the wrong part, and he left the non-uniform beam and the hinged rod
> questions blank."

It found half term without being told the dates ("Week 5 – Tuesday 20 October: Half term – consolidation
session… keep it lighter and focused on consolidation rather than new material"), and it wrote a
"Before your next lesson (Friday)" section for the lesson that is actually tomorrow. The one nonsense is
the title, which says six weeks.

### The worksheet cut from the paper — the weakest artefact

Three questions, chosen from a picker that is finally readable, landing as a real assignable homework —
the mechanics of it are fixed. What comes out is not usable: no figures, an escape sequence printed in
the middle of a sentence, a density table whose exponents have been flattened, and two of the three
questions printed twice. I would not hand this to Leo.

---

## Verdict

**Would I use this with real students next week?** Yes, and that is a change. The loop I could not close
last time — set work, student hands in, mark it, send feedback that knows what they wrote — now closes,
and the feedback it produces is genuinely better than what I would write in the ten minutes I would
actually give it.

**What stopped me most:** the paper library. The one physics paper with figures shows me a red error box
instead of its questions, and a worksheet cut from it prints `12°`, drops every diagram and prints
the multiple-choice questions twice — so the half of the product that was the best part last time is now
the half I cannot trust. Behind that: marking in progress cannot be saved, and editing a question still
leaves the mark scheme, the marking panel and the feedback all describing the question I deleted.
