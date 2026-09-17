# Admin re-trial — Sidereal Tutoring

Second pass as the technical owner of a small tutoring agency, after a round of fixes. Same rules
as before: browser only (Chromium, 1440×900 and 400×900), no API calls, no database, no reading the
source. Every finding in `admin.md` was re-checked. Screenshots in `.screenshots/trial2-admin/`.

Scenario run: signed in, created tutor **Priya Ramanathan** (`priya.trial2@sidereal.example.com`)
with a generated password, worked the Dashboard / Jobs / Tutors / Topics screens, waited out a full
tutor session and a full student session, reviewed what they left behind, then tore the tutor down.
Two Retry clicks were the only generation I caused: one paper extract (ran, failed again) and one
homework retry (rejected, no job created).

## Every finding from `admin.md`

| # | Finding | Status | Evidence | Screenshot |
|---|---|---|---|---|
| B0 | Tutor who uploaded a file can never be removed (500) | **Closed** | Priya had uploaded lesson notes at 16:18; Remove returned 204, the row vanished, toast "Removed" | `57-remove-result.png` |
| B0b | "Still has students" error renders behind the modal overlay | **Closed** | 409 toast paints above the scrim, fully legible: "This tutor still has 1 student." (pluralisation fixed) | `63-remove-blocked-by-archived-student.png` |
| B0c | Archiving a student does not release them from their tutor | **Still open** | Archived test student still counted "1" on the Tutors row and still produced a 409; the Archive dialog never mentions the tutor | `62-student-archived.png` |
| B0d | A suspended tutor is told their password is wrong | **Still open** | Suspended Priya, signed in as her: "Could not sign in. Check the email and password." | `55-suspended-signin.png` |
| B1 | Tutors table overflows the viewport at 400 px | **Closed** | Table becomes cards; scrollWidth 400 = clientWidth 400; Reset password / Suspend / Remove all on screen | `28-mobile-400-tutors.png` |
| B2 | The agent service account is listed and managed as a tutor | **Closed** | Row reads "Service account" where a student count would be, and offers no actions at all | `05-tutors-list.png` |
| B3 | A failed job tells you nothing and there is no retry | **Closed** | Expanded failed job now has a Retry button; my retry ran and failed with a specific reason | `17-job-failed-expanded.png`, `45-retried-job-failed.png` |
| B4 | Jobs never refresh and there is no Refresh button | **Closed** | Refresh button present, and the page polls on its own — 31 `/api/admin/jobs` fetches in 90 s with a job Generating | `26-jobs-live-45s.png`, `27-jobs-live-90s.png` |
| B5 | Material counted on the dashboard and shown nowhere | **Partly** | Tutor uploads now appear in the Library, but dashboard MATERIAL 15 against 13 Library items — two still counted and unreachable | `50-library-after-trial.png`, `66-dashboard-final.png` |
| B6 | "Data model" dead-ends at a second, unbranded login | **Partly** | Label is now "Directus (separate sign-in)" and opens in a new tab, so you keep your place; the destination is still Directus's "Not Authenticated" screen and the app supplies no credentials | `43-directus-link.png` |
| B7 | Unknown admin URLs silently redirect to the tutor home | **Still open** | `/admin/nonexistent`, `/admin/students`, `/admin/costs` all land on `/` with no 404 and no message | `37-admin-404.png` |
| B8 | Two extractions of the same paper disagree, nothing flags it | **Partly** | Still the same Physics paper at 31 and 53 questions among 12 drafts, unflagged — but a paper now has Delete, Mark reviewed and per-question editing, so it can be acted on | `41-library-papers.png`, `42-paper-detail.png` |
| C1 | Generated password cannot be copied and vanishes on submit | **Still open** | Still no copy control; "Copy it now — it is not shown again" over a plain field, then the dialog closes on "Tutor added" | `10-generated-password.png`, `12-tutor-created.png` |
| C2 | "Hand those over first" — but the admin app has no hand-over | **Still open** | Remove dialog copy unchanged; reassignment is still a dropdown on the student's page in the tutor app | `56-remove-dialog.png`, `61-reassign-dropdown.png` |
| C3 | Job rows show input but never output | **Still open** | A Done job's panel is INPUT JSON with bare UUIDs — no artefact link, no duration, no tokens, no cost | `19-job-done-expanded.png` |
| C4 | The Reset password dialog does not say whose password | **Still open** | Title is "Reset password", one bare field, launched from a row in a multi-row table | `14-reset-password-dialog.png` |
| C5 | The admin's "Tutor app" silently shows every tutor's students | **Still open** | Amara (Unassigned) and Priya's Trial Student Leo, no banner, and the ADMIN badge disappears from the sidebar | `39-tutorapp-students-as-admin.png` |
| C6 | Topic depth is unreadable without clicking | **Still open** | `Particles` (child of Physics) sits 19 px from `Moments` (child of Mechanics) and directly beneath it; chevrons still only on parents | `32-topics.png`, `31-mobile-400-topics.png` |
| C7 | The Library credits me with material I never uploaded | **Partly** | The 10 seeded items still read "by You" on the admin account, but live uploads now name the uploader ("by Priya Ramanathan") | `40-library.png`, `50-library-after-trial.png` |
| C8 | Error copy quality is inconsistent | **Closed** (new runs) | The retry failed with "No call transcribed question 11, 12, so the paper would carry a one-line summary where its wording belongs. Try the extraction again." Old rows keep the old vague text | `45-retried-job-failed.png` vs `18-paper-extract-failed.png` |
| C9 | Jobs mixes names and email addresses in adjacent columns | **Still open** | STUDENT "Trial Student Leo", TUTOR "priya.trial2@sidereal.example.com" | `46-jobs-tutor-email-column.png` |
| C10 | `model: fake` is shown to the admin | **Still open** | The three seeded Amara rows still report MODEL `fake` | `16-jobs-list.png` |
| C11 | The Generation status card has no up/down dot | **Still open** | Three cards show "• Up"; Generation shows only `openrouter` and a model id | `04-dashboard.png` |
| C12 | `/account` drops the admin navigation | **Partly** | Still renders in the tutor shell, but that shell now carries an "Admin" link, so the back button is no longer the only way out | `36-account.png` |
| C13 | Validation reports one error at a time; missing reads as malformed | **Still open** | Empty form and `not-an-email` both give "Enter the email address the tutor will sign in with."; the password error only appears once the email passes | `07-empty-submit.png`, `08-bad-email-short-pw.png`, `09-short-pw.png` |
| C14 | Sign-in gives no feedback for ~4 s | **Closed** | The button disables and reads "Signing in…"; sign-in completed in 0.4 s | `02b-login-pressed.png` |
| C15 | The tutor's private note about a named student is shown on admin Jobs | **Still open** | The expanded INPUT still carries "Leo keeps using the along-beam distance" verbatim | `25-retry-homework-silent.png` |
| C16 | Suspend is one unconfirmed click; Remove confirms | **Still open** | Suspend flipped Active → Suspended with no dialog. (Archive on a student did gain a confirmation) | `54-tutor-suspended.png` |
| C17 | Reassigning a student is an unconfirmed dropdown | **Still open** | The Tutor select has no label, applies on change, and shows no confirmation or toast | `61-reassign-dropdown.png` |
| M1 | Topics cannot be applied to anything | **Partly** | `Moments` now reads MATERIAL 3 and the Library has a topic filter — but QUESTIONS and HOMEWORK stayed 0, and nothing on an admin screen does the tagging | `33-topic-detail.png`, `40-library.png` |
| M1b | Students cannot be deleted | **Closed** | Delete sits beside Edit and Archive, behind a dialog that spells out exactly what goes | `64-delete-student-dialog.png` |
| M2 | No admin view of students, sessions or material | **Still open** | Admin nav is still Dashboard / Tutors / Jobs / Topics; everything else is the borrowed tutor app | `66-dashboard-final.png` |
| M2b | Student activity is invisible to the admin | **Still open** | A whole student session — opening, attempting, handing in, being marked — moved Jobs from 24 to 26, and both new rows were the tutor's Feedback and Study plan | `49-jobs-after-trial.png` |
| M3 | No hand-over action on the Tutors page | **Still open** | Row actions are still Reset password / Suspend / Remove; no reassign, no bulk reassign | `58-tutors-final.png` |
| M4 | No retry or cancel on a job | **Partly** | Retry now exists on a failed job; a Generating job still has no cancel | `17-job-failed-expanded.png` |
| M5 | No way to send a tutor their credentials | **Still open** | No invite, no reset link — the dialog is Email / names / Password / Generate | `06-add-tutor-dialog.png` |
| M6 | Topics cannot be moved, reordered or merged | **Still open** | Row controls are only "Add a subtopic under X", "Rename X", "Delete X" | `32-topics.png` |
| M7 | No cost or usage figure anywhere | **Partly** | A paper's header now reads "Generated by anthropic/claude-sonnet-5 from 2 pieces of material · $1.31 · 32 calls" — but no admin screen shows spend, and the Jobs panel carries none | `42-paper-detail.png`, `19-job-done-expanded.png` |
| M8 | No audit trail | **Still open (worse)** | Jobs is still the only history, and it now loses its attribution — see N2 | `49-jobs-after-trial.png` |
| M9 | No "unassigned students" signal | **Partly** | The tutor app's student list now shows "Unassigned" against Amara; no admin screen says it | `51-students-everyone.png` |
| M10 | The generated password is weak | **Still open** | 12 characters, lowercase and digits only (`hh66q425vjmm`), no policy | `10-generated-password.png` |
| Copy 1 | "Copy it now — it is not shown again." | **Still open** | No copy control, nothing shows it again | `10-generated-password.png` |
| Copy 2 | "The generated result could not be used. Try again." | **Closed** | There is now a Try again, and new failures say why | `45-retried-job-failed.png` |
| Copy 3 | "A tutor with students cannot be removed — hand those over first." | **Still open** | Hand-over still exists on no admin screen | `56-remove-dialog.png` |
| Copy 4 | "Material every tutor can use." | **Partly** | Tutor uploads are listed there now; the dashboard still counts two the Library does not show | `50-library-after-trial.png` |
| Copy 5 | "Tag material, questions and homework." | **Partly** | Material tagging works; the QUESTIONS and HOMEWORK counters never left 0 | `52-topics-after-trial.png` |
| Copy 6 | "Enter the email address the tutor will sign in with." for a malformed address | **Still open** | Identical message for empty and for `not-an-email` | `08-bad-email-short-pw.png` |
| Copy 7 | "Their sign-in goes for good." | **Closed** | It now does — the removal succeeds | `57-remove-result.png` |
| Copy 8 | "Could not sign in. Check the email and password." to a suspended tutor | **Still open** | Unchanged message; see also N3 | `55-suspended-signin.png` |
| Copy 9 | "This tutor still has 1 student(s)." | **Closed** | Now "This tutor still has 1 student." | `63-remove-blocked-by-archived-student.png` |

Tally: 13 closed, 8 partly, 24 still open.

## New findings, ranked

**N1 — Retry on a job whose student was deleted fails with a raw database error.** *High.*
Expand the failed Homework of 17 Sept 14:36 (its student was deleted in the last trial) and click
Retry. The toast reads, verbatim: *Directus 400: Invalid foreign key
"2b3935a3-bf8b-4b9f-a127-98662202f0b5" for field "student" in collection "generation_jobs".* No job
is created, the row stays Failed, and the panel shows no error. This is the old B0 failure mode
moved to a new button — the only difference is that the raw message now reaches the screen instead
of being swallowed. `25-retry-homework-silent.png`

**N2 — Deleting a student erases the attribution on every job it produced.** *High.*
While Trial Student Leo existed, his Homework job read "Trial Student Leo / priya.trial2@…". After
the tutor deleted him, the same row reads "— / —", and so do the Feedback and Study plan that
followed. 15 of the 26 rows on the Jobs page are now unattributable, and the delete dialog's promise
that "the generation history is kept" is only half true: the runs are kept, the record of who ran
them is not. Jobs is the only history the admin has. `46-jobs-tutor-email-column.png` (before) vs
`49-jobs-after-trial.png` (after)

**N3 — The suspended-account check is wired up but dead in this deployment.** *Medium.*
Signing in as a suspended tutor fires `POST /api/auth/status`, which returns 503:
`{"code":"service_token_missing","message":"This deployment cannot check an account's standing. Ask
an administrator."}` So the machinery that would have fixed B0d exists and never fires, the tutor
gets the generic "check the email and password", and nothing anywhere tells the admin the check is
switched off. `55-suspended-signin.png`

**N4 — Removing a tutor silently orphans their shared-library uploads.** *Medium.*
Priya's "Moments and equilibrium - lesson notes" stayed in the Library after she was removed,
relabelled "by A colleague". The Remove dialog says only "Their sign-in goes for good" — it does not
mention the material, and afterwards there is no way to tell which items were theirs.
`60-library-final.png`

**N5 — Topic counters do not roll up to parents.** *Medium.*
`Moments` shows MATERIAL 3; its parent `Mechanics` shows 0 and the root `Physics` shows 0. An owner
reading the tree concludes there is no Physics material at all. `52-topics-after-trial.png`

**N6 — A signed-in admin lands in the tutor app, not the admin dashboard.** *Low/Medium.*
Signing in as `admin@sidereal.example.com` lands on `/` — the tutor Home, "Nothing in the diary this
week" — with the ADMIN badge absent from the sidebar. The admin dashboard is one more click away,
behind a nav item named "Admin". `03-after-login.png`

**N7 — The topic counters are dead ends.** *Low/Medium.*
"3 MATERIAL" is not a link and nothing on the page lists the three items. The dashboard counts were
made clickable in this round; these were not. `33-topic-detail.png`

**N8 — After a 409 the Remove dialog sits unchanged, still inviting the click.** *Low.*
The toast explains the block, but the dialog shows no inline error and the red Remove button stays
enabled — click it again and you get the same toast. `63-remove-blocked-by-archived-student.png`

**N9 — Provenance vocabulary is inconsistent within one column.** *Low.*
The same "by …" line reads "by You", "by A colleague", "by Priya Ramanathan" and "by Sidereal Agent"
depending on who and whether they still exist. Two items uploaded during the previous trial read "by
A colleague" while one from this trial reads "by Priya Ramanathan", with nothing to say why.
`41-library-papers.png`, `50-library-after-trial.png`

## State left behind

Priya Ramanathan removed; no trial student remains. Tutors: **Sidereal Agent** only. Students:
**Amara Okafor** only (still unassigned, untouched). The Physics topic tree, the library, the papers
and Amara are as I found them.

Residue I could not remove through the admin UI, all of it disclosed rather than cleaned up so as
not to touch shared data: the lesson-notes upload Priya added to the shared Library during the trial
(now "by A colleague"); the three job rows from the tutor's session and the one failed Paper extract
my Retry produced — jobs cannot be deleted. Dashboard MATERIAL therefore reads 15 against 13 Library
items.

## Verdict

Yes, for the first hour — and still no, for the second. Everything that stopped me last time on the
way *in* has been fixed: a tutor can be created, suspended and genuinely removed, the mobile layout
holds, failed jobs explain themselves and can be retried, and a student can finally be deleted.

What is still missing is everything that happens *after*: the admin's only record of what was done
erases itself when a student is deleted, a whole student session leaves no trace at all, spend is
recorded per artefact and never totalled, and the one hand-over the Remove dialog tells you to
perform still exists on no admin screen.
