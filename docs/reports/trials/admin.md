# Admin trial — Sidereal Tutoring

Role played: technical owner of a small tutoring agency, setting the app up for a new tutor.
Everything below was done in a browser (Chromium, 1440×900, one pass at 400×900). No API calls,
no database, no reading the source. Screenshots in `.screenshots/trial-admin/`.

## What I did, and what happened

### 1. Sign in

`http://localhost:5173/` redirects to `/login`. One card, email + password, no "forgot password"
link and no product explanation. Signed in as `admin@sidereal.example.com`; landed on `/admin`.
Took about 4 s with no spinner or disabled button — I could not tell whether my click registered.
`01-landing.png`, `02-login-filled.png`, `03-after-login.png`

### 2. Take stock of the dashboard

Four status cards (Directus, App, Typesetting, Generation) and one strip of counts: TUTORS 1,
STUDENTS 1, MATERIAL 12, JOBS RUNNING 0. That is the whole page — three-quarters of the screen is
empty. Nothing is clickable: the counts are not links, so "1 student" is a dead end. The Generation
card is the only one with no up/down dot, so I could not tell whether generation was actually
reachable or just configured. The card names the vendor and model id (`openrouter`,
`anthropic/claude-sonnet-5`) — useful to me, meaningless to an agency owner, and it is the only
place in the app that says anything about spend. There is no cost figure anywhere.
`04-dashboard.png`

### 3. Tutors

The list had exactly one row: **Sidereal Agent / agent@sidereal.example.com**, Active, 0 students,
never signed in — with Reset password, Suspend and Remove next to it. That is the machine service
account presented as a member of staff. Nothing on the screen says so. My first instinct as a new
owner was "who is this, and can I delete it?" — and the UI happily offers to. `05-tutors-list.png`

Also: the existing student Amara Okafor belongs to nobody, and the Tutors page cannot tell me that.
It reports students-per-tutor but never "1 student has no tutor".

### 4. Create the tutor

`Add tutor` → a clean dialog: Email, First name, Last name, Password with a Generate button.
Generate produced twelve characters of lowercase letters and digits only. The helper
text reads *"Copy it now — it is not shown again"* and there is no copy button; the only way to keep
it is to select the text by hand. On submit the dialog closes and the password is gone for good —
no confirmation screen, no "here is the credential, send it to Priya". Toast: "Tutor added".
`06-add-tutor-dialog.png`, `07-add-tutor-filled.png`, `08-tutor-created.png`

I then deliberately retried with the same email: *"That tutor could not be created. The email may
already be in use."* — good. Submitting empty gives "Enter the email address the tutor will sign in
with."; a malformed email gives the identical message, so you cannot tell "missing" from "wrong".
A one-character password gives "At least 8 characters — or use Generate." — but only after the email
passes, one error at a time. `31-duplicate-email-error.png`, `39-empty-submit.png`,
`40-bad-email-short-pw.png`, `41-one-char-password.png`

Credentials written to the agreed scratchpad path immediately after creation.

### 5. Jobs

18 rows. Fifteen are titled **"Paper extract"** and nothing else — same title, same model, no paper
name, no document name, no way to tell one from another. Student and Tutor are `—` on all fifteen.
Three seeded rows (Study plan / Feedback / Homework for Amara) show model **`fake`**, which reads
like a bug to anyone who does not know the fixtures. `09-jobs-list.png`

Rows expand from a chevron in the first cell (clicking the row body does nothing). A **done** job
shows one thing: INPUT, as raw JSON with bare UUIDs. No output, no link to the paper it produced, no
duration, no token count, no cost. `11-job-done-expanded.png`

A **failed** job shows ERROR: *"The generated result could not be used. Try again."* — no cause, no
stage, and no Try again button anywhere. Three of fifteen extractions failed and as admin I have no
idea why, on what, or what to do. `10-job-failed-expanded.png`

The status filter (Every job / Queued / Generating / Done / Failed) works; Queued shows "No jobs with
that status." `12-jobs-queued.png`, `12-jobs-failed.png`

The page does not refresh itself and has no Refresh button. While a tutor's Homework job was
Generating, I left the page open 90 s and nothing moved; only a browser reload updated it. The
dashboard has a Refresh button; the page that actually changes does not.
`43-jobs-live-check.png`, `44-dashboard-jobs-running.png`

### 6. Topics

Empty: "No topics yet — start with a broad one like Algebra." Added `Physics`, then used the "+"
on a row to add `Mechanics` under it, `Moments` under Mechanics, and `Particles` under Physics.
This worked first time and the icon buttons have proper labels ("Add a subtopic under Physics").
The detail panel shows a breadcrumb, a description box, and MATERIAL / QUESTIONS / HOMEWORK counters.
`13-topics-empty.png` … `19-topics-tree.png`

Two problems. The counters are permanently 0 and there is nothing anywhere an admin can reach that
attaches a topic to the 10 library items or 12 papers — I built a taxonomy that cannot be applied.
And the tree's depth is hard to read: chevrons only render on nodes that have children, so `Particles`
(a child of Physics) sits within ~20 px of `Moments` (a grandchild), and I had to click each node and
read the breadcrumb to confirm I had built the tree I meant to. `28-mobile-400-topics.png` shows it
most clearly. There is no way to move, reorder or merge a topic — a mis-parented node has to be
deleted and retyped.

### 7. Tutor app, as admin

"Tutor app" in the sidebar drops you into the tutor Home at `/`. It shows **every** tutor's students
and sessions — Amara (Unassigned) and Trial Student Leo (Priya's) — with no banner saying you are
looking at all tutors' work rather than your own. The nav swaps entirely to the tutor nav; the only
way back is an "Admin" link. `20-tutor-app-as-admin.png`, `21-tutorapp-students.png`

Library: "Material every tutor can use" — 10 items, all marked **"by You"** even though I had just
created this account's first session and uploaded nothing. Papers tab: 12 drafts, none published,
with obvious duplicates — the same AQA A-level Maths 2023 paper three times, the same GCSE Maths
paper twice, and the same A-level Physics paper extracted twice with **31 questions vs 53 questions**
(both 85 marks). As admin I can see that one of those extractions is wrong and there is no way to act
on it. `22-tutorapp-library.png`, `24-tutorapp-library-papers.png`, `37-library-papers.png`

The student page does have a Tutor selector (Nobody / Sidereal Agent / Priya Ramanathan) — so
hand-over exists, but it lives on each student's page inside the tutor app, not on the Tutors screen
where the admin is told to do it. `34-student-amara-as-admin.png`

I left Amara alone, as instructed.

### 8. Other things I tried

- **Data model** (sidebar) opens `localhost:8055/admin/settings/data-model` and lands on a second,
  differently-branded **Directus login** saying "Not Authenticated". My Sidereal session does not
  carry over. `38-data-model-directus.png`
- **`/account`** renders inside the *tutor* shell — the admin nav disappears and I had to use the
  browser back button. `30-account.png`
- **`/admin/nonexistent`** silently redirects to the tutor home. No 404, no message. `42-admin-404.png`
- **400 px**: Dashboard, Jobs and Topics are fine (Jobs scrolls its table inside its card). The
  **Tutors** table does not — the whole document scrolls sideways (615 px of content in a 400 px
  viewport), the header bar paints only the first 400 px, and Reset password / Suspend / Remove are
  off-screen. `26-mobile-400-tutors.png` vs `27-mobile-400-jobs.png`
- Dashboard counts updated correctly as the tutor worked (TUTORS 2, STUDENTS 2, JOBS RUNNING 1),
  but MATERIAL went 12 → 13 while the Library still lists **10**. No screen in the app reconciles
  that number. `35-dashboard-after-tutor-work.png`, `36-library-material-count.png`

### 9. Reviewing the trial, and tearing it down

Both agents finished. What the admin could see of ~40 minutes of tutor and student work:

**Jobs** gained four rows, all correctly attributed to Trial Student Leo and Priya: a Homework that
**failed**, a Homework that succeeded eight minutes later, a Feedback and a Study plan. The failure
message here is genuinely good — *"The answer was cut off before it was finished. Try again with less
material."* — and the INPUT shows the tutor's full brief, including her private note that "Leo keeps
using the along-beam distance". Nothing the **student** did produced a row, or any other trace an
admin can see: I could tell that homework was generated, not that it was ever opened, attempted or
submitted. `47-jobs-after-trial.png`, `45-tutor-homework-job-failed.png`

**Students**: Trial Student Leo had been archived, not deleted (Archived tab), still assigned to
Priya, with a Study plan, Feedback and a Marked homework on his overview. `51-students-everyone-tab.png`,
`55-trial-student-page.png`

**Dashboard**: TUTORS 2, STUDENTS 2, MATERIAL 14, JOBS RUNNING 0. The shared Library still lists
**10**. The four material items the tutor and student created during the trial are counted on the
admin dashboard and appear on no screen the admin can reach. `61-dashboard-final.png`,
`63-library-final.png`

**Suspend** worked: one click, no confirmation dialog, status flipped to Suspended and the action
became Reactivate. I then signed in as Priya in a clean browser and was refused — but with *"Could
not sign in. Check the email and password."* A suspended tutor is told their password is wrong and
will go asking for a reset. `53-tutor-suspended.png`, `64-suspended-tutor-signin.png`

**Remove failed twice, and I could not complete the teardown.**

First attempt, with Leo still attached: `DELETE /api/admin/tutors/…` returned **409**. The dialog
stayed open, unchanged. There *was* an error toast — "This tutor still has 1 student(s). Reassign
them to another tutor first." — but it rendered in the bottom-right corner **behind the modal's dim
overlay**, washed out and easy to miss entirely. Note also that Leo was *archived*; archiving a
student, which is the only "finish with a student" action the product has, does not release them
from the tutor. `54-remove-blocked-by-student.png`

So I used the only hand-over that exists — the Tutor dropdown on Leo's own page — and set him to
Nobody. Instant, no confirmation. The Tutors row then correctly read 0 students.
`57-student-unassigned.png`

Second attempt, 0 students: `DELETE /api/admin/tutors/…` returned **500**:

```
{"detail":{"code":"directus_rejected","message":"Directus 500: delete from \"directus_users\"
where \"id\" in ($1) - update or delete on table \"directus_users\" violates foreign key constraint
\"directus_files_uploaded_by_foreign\" on table \"directus_files\""}}
```

The UI showed **nothing at all** — no toast, no inline error, no change. The dialog simply sat there
with the Remove button still inviting another click. `62-remove-attempt-2.png`

Because Priya had uploaded one file during the trial, she cannot be removed, and the app never says
so. There is no delete action for a student anywhere (only Archive / Unarchive and "Remove login"),
and the file that blocks the deletion is one of the four items invisible to the admin, so there is no
UI route to clear the blocker either.

**Final state left behind** (browser-only teardown, nothing else deleted):
Priya Ramanathan — **Suspended**, 0 students, sign-in dead; not removable through the UI.
Trial Student Leo — archived, tutor set to Nobody.
The Physics › Mechanics › Moments / Physics › Particles topics from step 6 — left in place.
Amara Okafor, the library, the papers and the other accounts — untouched.


## Findings, ranked

### Bugs

**B0 — A tutor who has uploaded a file can never be removed, and the app says nothing.** *Critical.*
Repro: create a tutor, sign in as them, upload one piece of material, sign out; as admin go to
`/admin/tutors`, ensure they have 0 students, click Remove → Remove. `DELETE
/api/admin/tutors/<id>` returns **500** with a raw Postgres foreign-key error
(`directus_files_uploaded_by_foreign`). The dialog does not close, no toast appears, no inline error
appears, the row does not change — the click is indistinguishable from doing nothing. The only
deletion the admin app offers is broken for any tutor who has actually used the product, and the
blocking file is one the admin cannot see (see B5). Suspend is the only real teardown available.
`62-remove-attempt-2.png`

**B0b — The "still has students" error renders behind the modal overlay.** *High.*
Same screen, with a student attached: the 409 does produce a toast — "This tutor still has 1
student(s). Reassign them to another tutor first." — but it paints in the bottom-right corner
underneath the modal's dim scrim, greyed out, while the dialog itself shows no error. I only found
it by inspecting the screenshot. (Also: "1 student(s)".) `54-remove-blocked-by-student.png`

**B0c — Archiving a student does not release them from their tutor.** *Medium.*
Leo was Archived — the only "done with this student" action the product has — and still counted
against Priya's removal. Nothing in the archive flow or the Remove dialog mentions this.
`51-students-everyone-tab.png`, `54-remove-blocked-by-student.png`

**B0d — A suspended tutor is told their password is wrong.** *Medium.*
Suspend Priya, then sign in as her: "Could not sign in. Check the email and password." She will ask
the admin for a password reset rather than learn she was suspended, and the admin has no way to know
that is the message she is getting. `64-suspended-tutor-signin.png`

**B1 — Tutors table overflows the viewport at 400 px; every action is unreachable.** *High.*
Sign in as admin at 400×900 and open `/admin/tutors`. The document's scrollWidth is 615 px against a
400 px viewport, so the whole page scrolls sideways instead of the table scrolling inside its card;
the header bar paints only the first 400 px, leaving a white band, and Reset password / Suspend /
Remove are entirely off-screen. `/admin/jobs` at the same width contains its table correctly, so the
pattern exists and simply is not applied here. `26-mobile-400-tutors.png` (compare
`27-mobile-400-jobs.png`)

**B2 — The agent service account is listed and managed as a tutor.** *High.*
`/admin/tutors` row 1 is "Sidereal Agent / agent@sidereal.example.com", Active, with Reset password,
Suspend and Remove offered. Nothing marks it as a machine account. A new owner tidying up their staff
list will suspend or remove the account the agent surface runs on, and the UI will let them.
`05-tutors-list.png`

**B3 — A failed job tells you nothing you can act on, and there is no retry.** *High.*
`/admin/jobs` → expand any Failed "Paper extract": ERROR reads *"The generated result could not be
used. Try again."* There is no Try again control anywhere on the page, no indication of which
document or stage failed, and the INPUT block is raw JSON with bare UUIDs. Three of fifteen
extractions failed and I could not diagnose or re-run a single one.
`10-job-failed-expanded.png`

**B4 — Jobs never refresh and the page has no Refresh button.** *Medium.*
Open `/admin/jobs` while a job is Generating and leave it. After 90 s nothing had changed; only a
browser reload updated the row. The Dashboard — which changes rarely — has a Refresh button; Jobs,
the one screen that moves, does not. `43-jobs-live-check.png`, `44-dashboard-jobs-running.png`

**B5 — Material the tutor and student created is counted on the dashboard and shown nowhere.**
*High.* Dashboard MATERIAL went 12 → 13 → 14 across the trial; the Library's Material tab listed 10
throughout. Four items exist that the admin is counted but cannot open, audit or delete — and one of
them is the file that makes B0 unfixable. `35-dashboard-after-tutor-work.png`,
`61-dashboard-final.png`, `63-library-final.png`

**B6 — "Data model" dead-ends at a second, unbranded login.** *Medium.*
Sidebar → Data model opens `localhost:8055/admin/settings/data-model` and lands on a Directus login
screen reading "Not Authenticated". The Sidereal session does not carry over, and the owner has no
Directus credentials from anything the app told them. `38-data-model-directus.png`

**B7 — Unknown admin URLs silently redirect to the tutor home.** *Low.*
`/admin/nonexistent` lands on `/` with no 404 and no message — a mistyped or stale bookmark looks
like a permission change. `42-admin-404.png`

**B8 — Two extractions of the same paper disagree and nothing flags it.** *Medium (data quality).*
The Papers tab holds 12 drafts including the same AQA A-level Physics 7408/1 paper extracted twice,
once as 31 questions and once as 53, both 85 marks; the same A-level Maths 2023 paper appears three
times and the same GCSE Maths paper twice. As admin I can see that at least one extraction is wrong
and there is no way to compare, mark, merge or discard them. `37-library-papers.png`

### Confusing — what I expected vs what I saw

**C1 — The generated password cannot be copied and vanishes on submit.** *High.*
The helper text says "Copy it now — it is not shown again" and there is no copy button; after
clicking Add tutor the dialog closes and nothing shows the password again. I expected either a copy
control or a post-create confirmation showing the credential to send on. A non-technical owner will
lose the first tutor password they create. `07-add-tutor-filled.png`

**C2 — "A tutor with students cannot be removed — hand those over first" — but the admin app has no
hand-over.** *Medium.* The Remove dialog names a step that does not exist on any admin screen.
Reassignment turns out to live on each student's page inside the *tutor* app, unlinked from here.
`33-remove-dialog.png`, `34-student-amara-as-admin.png`

**C3 — Job rows show input but never output.** *Medium.*
I expected a finished job to link to what it produced. An expanded Done job shows only INPUT JSON —
no artefact link, no duration, no token count, no cost. Fifteen rows all titled "Paper extract" with
the same model and no paper name are mutually indistinguishable. `11-job-done-expanded.png`,
`09-jobs-list.png`

**C4 — The Reset password dialog does not say whose password.** *Medium.*
Its title is just "Reset password" with a bare password field, launched from a row in a multi-row
table. The Remove dialog names the tutor; this one does not, and it is the more dangerous of the two
to get wrong. `32-reset-password-dialog.png`

**C5 — The admin's "Tutor app" silently shows every tutor's students.** *Medium.*
Clicking Tutor app put me in a tutor Home listing Amara (unassigned) and Priya's Trial Student Leo,
with no banner explaining I was seeing all tutors rather than my own caseload, and the admin nav
replaced by the tutor nav. `20-tutor-app-as-admin.png`, `21-tutorapp-students.png`

**C6 — Topic depth is unreadable without clicking.** *Medium.*
Chevrons render only on nodes that have children, so `Particles` (child of Physics) sits ~20 px from
`Moments` (child of Mechanics) and reads as its sibling. I had to select each node and read the
breadcrumb in the right-hand panel to confirm the tree I had just built. `19-topics-tree.png`,
`28-mobile-400-topics.png`

**C7 — The Library credits me with material I never uploaded.** *Low/Medium.*
All 10 seeded library items and 8 of the 12 papers read "by You" on the admin account, which makes
the provenance column worthless for working out who put what in. `22-tutorapp-library.png`

**C8 — Error copy quality is inconsistent.** *Medium.*
The tutor's failed Homework job says *"The answer was cut off before it was finished. Try again with
less material."* — specific and actionable. The paper-extract failures say *"The generated result
could not be used. Try again."* — neither. Same screen, same expander.
`45-tutor-homework-job-failed.png` vs `10-job-failed-expanded.png`

**C9 — Jobs mixes names and email addresses in adjacent columns.** *Low.*
STUDENT shows "Trial Student Leo", TUTOR shows "priya.trial@sidereal.example.com".
`45-tutor-homework-job-failed.png`

**C10 — `model: fake` is shown to the admin.** *Low.*
Three seeded rows report MODEL `fake`. To an owner reading the job log that looks like a defect or a
security problem. `09-jobs-list.png`

**C11 — The Generation status card has no up/down dot.** *Low.*
The other three service cards show "• Up". Generation shows only a vendor and a model id, so there is
no way to tell from the dashboard whether generation is reachable. `04-dashboard.png`

**C12 — `/account` drops the admin navigation.** *Low.*
Reached from the admin sidebar, it renders inside the tutor shell; the admin nav disappears and
the browser back button is the only way home. `30-account.png`

**C13 — Validation reports one error at a time, and "missing" reads the same as "malformed".** *Low.*
An empty form and `not-an-email` both produce "Enter the email address the tutor will sign in with.";
the password problem is only revealed after the email is fixed. `39-empty-submit.png`,
`40-bad-email-short-pw.png`, `41-one-char-password.png`

**C14 — Sign-in gives no feedback for ~4 s.** *Low.*
The button does not disable and no spinner appears; I clicked wondering whether it had registered.
`02-login-filled.png`

**C15 — The tutor's private notes about a named student are shown verbatim on the admin Jobs page.**
*Low, but a policy call.* The expanded INPUT for the Homework job contains "Leo keeps using the
along-beam distance". Defensible for an agency owner, but it is not disclosed anywhere and the
tutor has no way to know. `45-tutor-homework-job-failed.png`

**C16 — Suspend is one unconfirmed click; Remove confirms.** *Low.*
Suspend cuts off a tutor's sign-in instantly with no dialog and no undo prompt (Reactivate exists,
but you have to know that). Remove — which the app can barely perform (B0) — gets a full
confirmation. The confirmation is on the wrong button. `53-tutor-suspended.png`

**C17 — Reassigning a student is an unconfirmed dropdown.** *Low.*
The Tutor select on a student's overview applies on change, with no confirmation and no toast. It is
the app's only hand-over mechanism and also its easiest mis-click. `57-student-unassigned.png`

### Missing capabilities

**M1 — Topics cannot be applied to anything.** *High.* I can build a tree, and the detail panel
counts MATERIAL / QUESTIONS / HOMEWORK, but nothing an admin can reach tags a library item, a paper
or a question with a topic. The counters sat at 0 throughout. The taxonomy is inert.

**M1b — Students cannot be deleted.** *High.* Archive / Unarchive and "Remove login" are the only
lifecycle actions on a student, on the detail page and in the Edit dialog. Combined with B0 and B0c,
a trial, a duplicate or a mistaken student record is permanent, and so is the tutor attached to it.
`55-trial-student-page.png`, `56-student-edit-dialog.png`

**M2 — No admin view of students, sessions or material.** *High.* The admin sidebar is Dashboard /
Tutors / Jobs / Topics. Everything else is reached by borrowing the tutor app, which mixes admin into
tutor scope (see C5) and has no admin-only affordances (no "students without a tutor", no per-tutor
caseload view).

**M2b — Student activity is invisible to the admin.** *Medium.* A full student session — opening,
attempting and submitting homework — left no job row and no other trace anywhere in the admin app. I
could see that work was *generated*, never that it was *done*. `47-jobs-after-trial.png`

**M3 — No hand-over action on the Tutors page.** *High.* Referenced by the Remove dialog (C2) and
absent. There is also no bulk reassign when a tutor leaves.

**M4 — No retry or cancel on a job.** *High.* Three failed extractions and one failed homework, and
the admin can do nothing with any of them.

**M5 — No way to send a tutor their credentials.** *Medium.* No invite email, no reset link — the
admin must copy a password out of a field (which they cannot copy, see C1) and transmit it by hand.

**M6 — Topics cannot be moved, reordered or merged.** *Medium.* A mis-parented topic must be deleted
and retyped; there is no drag, no parent selector, and Add topic at the top always creates a root.

**M7 — No cost or usage figure anywhere.** *Medium.* The dashboard names the vendor and model but
never what has been spent, and job rows carry no token or cost figure — the one number an agency
owner will want before letting tutors generate freely.

**M8 — No audit trail.** *Medium.* Jobs is the only history. Nothing records that a tutor added a
student, changed an assignment, or deleted material.

**M9 — No "unassigned students" signal.** *Medium.* Amara has no tutor; the dashboard counts her and
the Tutors page reports 0/1 students per tutor, but nothing says a student is unowned.

**M10 — The generated password is weak.** *Low.* 12 characters, lowercase and digits
only, no way to set a policy. `07-add-tutor-filled.png`

### Copy that misled me

1. *"Copy it now — it is not shown again."* — there is no copy control, and nothing shows it again.
   `07-add-tutor-filled.png`
2. *"The generated result could not be used. Try again."* — there is no way to try again.
   `10-job-failed-expanded.png`
3. *"A tutor with students cannot be removed — hand those over first."* — hand-over does not exist on
   any admin screen. `33-remove-dialog.png`
4. *"Material every tutor can use."* — the dashboard counts material that is not in that list and
   that no tutor can see there. `22-tutorapp-library.png`, `35-dashboard-after-tutor-work.png`
5. *"Tag material, questions and homework."* — the subtitle of a page from which none of those three
   things can be tagged. `13-topics-empty.png`
6. *"Enter the email address the tutor will sign in with."* — shown for a malformed address, not just
   a missing one. `40-bad-email-short-pw.png`
7. *"Their sign-in goes for good."* — on a button that, for any tutor who has used the product, does
   nothing at all. `62-remove-attempt-2.png`
8. *"Could not sign in. Check the email and password."* — shown to a tutor whose account the admin
   suspended. `64-suspended-tutor-signin.png`
9. *"This tutor still has 1 student(s)."* — programmer pluralisation, in a message the admin cannot
   see anyway. `54-remove-blocked-by-student.png`

## Verdict

No. A non-technical agency owner can get as far as creating a tutor and a topic tree, but the moment
anything needs undoing they are stuck — removing a tutor silently does nothing, students cannot be
deleted, failed jobs cannot be diagnosed or retried, and the dashboard counts material that appears
on no screen they can open.

What stopped me most: clicking Remove on a tutor and watching the app do nothing at all — a 500 with
a raw database constraint behind it, no toast, no error, no clue — which left me unable to finish the
teardown I was sent here to do.
