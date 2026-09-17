# Tutor trial — Priya, A-level Physics and Maths

One session, 17 Sept 2026, 14:23–15:15. Chromium 1440×900 (one pass at 400 px), never the API or the
database, never the source. Screenshots in `.screenshots/trial-tutor/`.

Spend: homework $0.16 (125 s), feedback $0.01 (20 s), study plan $0.03 (40 s), one handwriting scan
(instant, no cost shown). A fourth homework run was triggered and vanished without a trace — see bug 4.

---

## What I did, and what happened

**Sign in (14:23).** Clean, two fields, no "forgot password". I had earlier typed `/account` while
signed out; after signing in it took me straight back there, which was the right thing to do.
`01-landing.png`, `02-login-400.png`.

**Look around (2 min).** Four things in the sidebar: Home, Students, Library, Topics. Home is three
empty panels — Upcoming sessions, To review, Material — with good empty copy ("The desk is clear").
No Sessions in the nav; sessions live inside a student. My own name in the sidebar is the only route
to the account page and it does not look like a link. `03-home.png`, `04-*.png`.

**Add a student (1 min).** Name, Level, Subjects (Enter after each), Notes. Worked first time, notes
carried through to the student page. It leaves you on the list rather than opening the new student.
`05`–`08`.

**Schedule a session (2 min).** "Schedule session" on the Overview does not open a dialog — it moves
you to the Sessions tab, where you press "Schedule session" again. After that: date, time, length
(prefilled 60), notes. It then reads "Tomorrow, 17:00", which is exactly right. `09`, `10`.

**Add material — pasted lesson notes (3 min).** Four modes: Upload / Paste a link / Paste text /
Scan handwriting. Paste text has a Name field, a Text box, Topics and a "From session" picker.
Ready in under a second, full text readable on the detail page. Topics said "No topics yet" at the
time, so I could not tag it; later, when the admin's tree appeared, tagging it *Physics › Mechanics
› Moments* worked fine. `12`–`16`, `45`, `46`.

**Library → the AQA Physics paper → a worksheet (12 min, most of it lost).** The paper renders
beautifully — real typeset maths, `⁴₂He`, mark allocations, ruled answer space — and the header
tells me it was extracted by Sonnet for $0.23. But the question text is SVG, so I cannot select it,
copy it, or Ctrl-F for "moments"; I scrolled 31 questions looking for mechanics.

Then I could not find "Make worksheet". I looked on the Questions tab (where the questions are), on
the Papers list, and on the student page. It is on the **Printable** tab. That cost me about six
minutes and I found it by accident. The picker itself is a ~3.5-row scroll box for 31 questions and
shows raw Typst (`Two stable isotopes of helium are $""^4_2"He"$ …`). I picked Q3 (gate and pulley —
genuine moments), Q22 (resolving a bearing) and Q25 (equilibrium of a parachutist), set "For a
student: Trial Student Leo" and "Due 2026-09-24".

What I got was a clean two-page PDF — and nothing else. It is a `blob:` URL in the dialog; it is not
in Leo's Material, not in his Homework, not in the Library. Close the dialog without downloading and
the work is gone. Worse, the PDF says "Figure 3 shows a garden gate…", "Figure 4 shows the pulley
arrangement…", "Figure 5 shows a plan view…", "Table 2 gives the density of three available
materials" — and contains none of them. Three of the five parts of Q3 cannot be answered from the
sheet. `17`–`24`.

**Generate homework (first attempt, silently lost).** Ticked Leo's notes plus the Physics question
paper, chose Typeset (PDF), wrote instructions, pressed Generate. "Generating… usually under a
minute." I refreshed the page while waiting. From that moment the job did not exist: "No homework
yet" on the Homework tab, "Nothing generated yet" on the Overview, "The desk is clear" on Home. I
waited six minutes and gave up. No error, anywhere. `27`, `29`, `30`.

**Generate homework (second attempt, worked).** Same inputs. 2 min 5 s, not "under a minute". The
result is good and I discuss it below. `31`, `32`.

**Edit one question.** The "Content" box is the raw Typst template, starting
`#let question-counter = counter("sidereal-question")`, with the hint "`#question[…]` numbers ·
`#answerlines(3)` rules lines". I replaced Q4(b) with a real physics part. Preview, Save, and the
PDF updated correctly. The "Questions" and "Answer" panel below it did **not** — it still shows the
old wording and the old mark scheme. `33`, `34`.

**Assign with a due date.** Due date field on the detail page, then "Assign". Status went Draft →
Assigned, "Due 24 Sept 2026". No friction. `35`.

**Set up a login (1 min).** Email, Generate password, "Copy it now — it is not shown again." Created
cleanly. `36`–`38`. Wrote `student.json` and handed over.

**Leo handed in (14:55).** Home surfaced it immediately: "To review — Moments and Equilibrium ·
handed in". The hand-in view is the best screen in the app: his typed answers, the photo of his
working, and the transcription underneath tagged "From the photo · Clear". `47`, `48`, `49`.

**Marking (10 seconds, because there is none).** The only control is "Finish marking". Pressing it
flipped the status to "Marked". There is no score, no per-question tick, no place to write a comment
on his working, no total out of the 25 marks the sheet is worth. I did not mark anything; I pressed a
button. `50`.

**Feedback.** The dialog offers "Material to work from" and the library — it will not let me select
the homework Leo just handed in. So I typed his performance into the Instructions box by hand. The
provenance line confirms it: "from 1 piece of material". 20 s, $0.01. "Mark sent" flips a status; it
does not send anything. `51`–`53`.

**Study plan.** Material, instructions, start and end date. 40 s, $0.03. It stops mid-sentence after
Week 1 of six — "End every example by writing" — and is saved and displayed as an ordinary Draft
with no warning. `54`, `55`.

**Handwriting scan.** Add material → Scan handwriting → photo, with an optional "Solutions to"
picker pointing at papers. Transcribed accurately and instantly. It took the filename as the title
("leo_hw") with no way to name it. `56`–`58`.

**Account page.** Complete and clear: photo, name, email, Light/Dark/System, change password, sign
out. Dark theme is properly done. `39`, `40`.

**400 px.** No horizontal overflow anywhere I looked; the student tab strip scrolls sideways, which
is the right call. `41b-student-400-dark-viewport.png`, `42`.

**Deleting Leo — could not.** "Remove login" fails with `Directus 500: An unexpected error
occurred.` Three times. And there is no Delete for a student at all, only Archive. I archived him.
`61`–`66`.

**Then I checked what archiving actually does.** I set a known password, signed in as archived Leo in
a clean browser, and landed on his home page: his lesson tomorrow, his new feedback, the lot. I then
reset his password to a generated value I did not record. `67`.

---

## Findings, ranked

### Bugs

**1 · Critical — "Remove login" always fails.** Student → Remove login → confirm. Toast:
`Directus 500: An unexpected error occurred.` `DELETE /api/students/{id}/login` returns 500. Three
attempts, two of them after a full reload. There is no other way to take a login away. The toast also
puts the word "Directus" in front of a tutor who has never heard of it. `63-remove-login-error.png`

**2 · Critical — Archiving does not revoke access.** Archive a student, then sign in as them: full
student app, homework, feedback, next lesson. Combined with bug 1 there is no working way to cut a
student off when they leave. `66-archived.png`, `67-archived-student-login.png`

**3 · Critical — The study plan was truncated and presented as finished.** Six-week plan, ends mid-
sentence in Week 1: "…End every example by writing". Saved as a normal "Draft" with no warning, no
retry, no indication anything went wrong. I would have sent that to a student.
`55-plan-generated.png`

**4 · High — A generation job disappears if you refresh, and a failed one leaves no trace.** Start
homework generation, refresh the page while "Generating…" is showing. The job is then invisible
everywhere — Homework tab, Overview "Latest work", Home "To review" — permanently, with no error. I
paid for a second run to get a result. The job id only lives in the tab that started it.
`27-generating.png`, `30-homework-tab-empty.png`

**5 · High — Editing homework content does not update the mark scheme.** Homework → Content → change
a question → Save. The PDF is regenerated correctly; the "Questions"/"Answer" panel below still shows
the pre-edit wording. The tutor then marks from a scheme that no longer matches the sheet the student
has. `34-homework-saved.png`

**6 · High — "Make worksheet" drops every figure and table.** The exported Q3 says "Figure 3 shows a
garden gate…", "Figure 4 shows the pulley arrangement…", "Figure 5 shows a plan view…", "Table 2 gives
the density of three available materials". None are in the PDF. Parts (2), (3) and (4) are
unanswerable. `23-worksheet-made.png`

**7 · Medium — Raw Typst leaks into every tutor-facing list.** "A uniform plank $A B$ has length
$4.0$ m and weight $150$ N", "at an angle of $30°$", and in the scan "Moment $= F x d = 12 x 0.4 =
4.8$ Nm". The PDF is perfect; the screen looks broken. `32-homework-detail.png`, `58-scan-detail.png`

**8 · Medium — Same leak in the worksheet question picker**, where it matters most because it is the
only place you can read the questions as text: `$""^4_2"He"$`, `$beta^-$`, `$5.2 times 10^(-7)$`.
`21-make-worksheet-dialog.png`

**9 · Low — One library row wraps.** "AQA A-level English Literature A 7712/1 June 2022 — question
paper" pushes its date and author onto a second line while every other row is single-line.
`04-library.png`

### Missing capabilities a tutor needs

**10 · Critical — There is no marking.** "Finish marking" is a status toggle. No mark, no score out
of 25, no per-question right/wrong, no annotation on the student's working, nothing that reaches the
student. The sheet carries mark allocations and the mark scheme carries method marks, and neither is
usable. This is the single thing I would do with a real hand-in and I cannot do it.
`50-finish-marking.png`

**11 · Critical — Feedback cannot read the hand-in.** The generate dialog offers documents only. I
had to retype "he answered Q1 and Q3 correctly but left Q2, Q4 and Q5 blank" into a free-text box.
Everything specific in the output is specific because I typed it. `51-feedback-dialog.png`

**12 · High — A worksheet is not assignable and is not saved.** "For a student" and "Due" print two
lines of grey text on a PDF and do nothing else. The worksheet never appears in the student's
Material or Homework, or in the Library. If you close the dialog without downloading, ten minutes of
question-picking is gone. `24-after-worksheet-student.png`

**13 · High — A student cannot be deleted.** Archive is the only option. I was asked to remove a trial
student and could not.

**14 · Medium — No way to see what a student sees.** I had to create a password and sign in as Leo to
find out. `67-archived-student-login.png`

**15 · Medium — Paper questions are not text.** SVG only: no select, no copy, no browser find. On an
85-mark paper that turns "find me the moments questions" into scrolling.

**16 · Medium — Two disconnected mark schemes.** The paper's "Mark scheme" tab says "No mark scheme
yet — Extract mark scheme", while "AQA A-level Physics 7408/1 June 2022 — mark scheme" sits in the
Library as a document. Nothing joins them. `19-paper-Mark-scheme.png`

**17 · Medium — Scan handwriting has no Name field.** The material is titled from the filename, so a
phone photo lands as "IMG_2931". `58-scan-detail.png`

**18 · Low — No "forgot password" on sign-in**, and the account page is reachable only by clicking
your own name in the sidebar, which is styled as a label.

### Copy that misled me

**19 · High — "Make worksheet" is on the wrong tab.** It lives on Printable. I looked on Questions,
on the Papers list and on the student page first. Six minutes. `19-paper-Printable.png`

**20 · Medium — "Generating… usually under a minute."** It took 2 min 5 s. I refreshed because of
that sentence, and lost the job (bug 4). `27-generating.png`

**21 · Medium — "Makes a PDF only — no homework is set."** True, clear, and directly above a "For a
student" picker and a "Due" date field that say the opposite. I believed the fields.
`21-make-worksheet-dialog.png`

**22 · Medium — "by A colleague" on every library item.** In a shared library I want to know whose
upload it is before I put it in front of a student. `04-library.png`

**23 · Medium — every paper is "Draft", unexplained.** As a new tutor I did not know whether a Draft
paper was safe to use. `17-library-papers.png`

**24 · Low — pasted text is labelled "Upload".** `15-material-added.png`

**25 · Low — "Mark sent" sends nothing.** `53-feedback-sent.png`

**26 · Low — the homework Content box is Typst source**, template and all, shown to a non-technical
tutor with the hint "`#question[…]` numbers · `#answerlines(3)` rules lines". Editing one question
means editing code. `32-homework-detail.png`

**27 · Low — the Papers list has three "AQA A-level Mathematics Paper 1 June 2023" and two
"A-level PHYSICS Paper 1" entries.** `17-library-papers.png`

---

## Quality of the generated work, judged as a physics tutor

### Homework — good. I would hand this to a student as it is.

I checked all five questions. The physics is right throughout: R_D = 90 N and R_C = 60 N on the
two-support plank; x = 3.3 m for the tipping condition; d⊥ = 1.25 m and M = 75 N m for the angled
force; d = 0.40 m for the non-uniform bar; T = 26.1 N and a hinge force of 26.1 N at 50° for the
hinged rod. The difficulty ramps properly and the last question is a real A-level question.

Best bit — it went straight at the mistake in my notes, twice. The cover line: *"Remember: moment =
force multiplied by the perpendicular distance to the pivot, not the distance measured along the
beam. Always give a unit with your final answer."* And Q3(c): *"Explain why using the distance AB
itself, instead of the perpendicular distance, would give the wrong answer. [1 mark]"* That is what I
would have written.

Worst bit — Q4(b): *"State one reason marks are commonly lost in this type of question, and how you
would avoid it. [1 mark]"* That is a revision tip lifted out of my notes and dressed up as an exam
question. No board asks it, and it burns a mark. I replaced it. Second worst, Q5(b)'s mark scheme
double-counts: one mark for the vertical component, one for the horizontal, then *"[1 mark for
setting up both equilibrium equations correctly]"* — which is the same two marks again.

The PDF is genuinely exam-like: mark allocations in the right margin, ruled answer space sized to the
question, no answers leaked into the student copy.

### Feedback — right shape, but it is only as good as what I typed.

Best bit: *"even if you get stuck partway, write down what you tried and where you got stuck. That's
more useful to bring to the session than a blank page."* Exactly the message. It also correctly
pointed him back at sections 1 and 3 of his own notes.

Worst bit: *"You had a go at extra working on the photo you attached, which is good practice for
showing your method even when you're not sure of the final answer."* It never saw the photo. Leo's
working reads "Total moment about pivot = 4.8 + 2.4 = 7.2 Nm" with an unexplained 2.4 that I would
want to ask about — and the feedback praises it sight unseen. That is the kind of line that costs you
a student's trust.

### Study plan — one sixth of a plan.

Best bit, the framing: *"Throughout, fix three specific habits: using the perpendicular distance (not
the along-the-beam one) when a force acts at an angle, stating the point moments are taken about, and
always giving units."* And it noticed half term without being told: *"Tuesday 27 October left free
for half term (use it for a homework catch-up, not a taught session)."*

Worst bit: it ends *"End every example by writing"*. Week 1 of six, mid-sentence, saved as a normal
draft. Unusable, and nothing on screen tells you so.

---

## Verdict

**Would I use this with real students next week?** For writing and printing homework, yes — the
generated sheet was better than what I would have typed in an hour, and the paper library and typeset
PDFs are the best part of the product. For anything after the student hands work back, no.

**What stopped me most:** there is no marking. I can set work, the student can hand it in, and then
the only thing the app lets me do is press "Finish marking" and watch a chip change colour — and the
feedback generator cannot read the hand-in either, so I end up retyping the student's performance
into a text box. Behind that, I could not remove a login (500 every time) and an archived student can
still sign in, which I would not put in front of a real family.
