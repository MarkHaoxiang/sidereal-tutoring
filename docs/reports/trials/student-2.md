# Student re-trial — Leo, 17, A-level physics

Re-trialled 17 Sept 2026, 16:31–17:27, on a 400×850 phone screen, with the homework page and
home screen checked again at 1440×900. Account: Trial Student Leo (`leo.trial2@…`).
Screenshots in `.screenshots/trial2-student/`.

Two things about the run itself, up front:

- **Only one homework was ever assigned to me.** I watched the Homework list for 45 minutes
  (16:33–17:03) and it never showed a second item, so there was no paper worksheet to open
  before the one I answered, and no figure anywhere to check. Everything below is the one
  sheet, *Moments and Equilibrium Practice*.
- **My account was deleted at 17:11, while I was still using it** — I found out because the app
  put me in the tutor's app and then refused my password. That cut the run short: I never got
  to read the feedback letter itself (I only saw its card in the list) or the study plan, and I
  could not re-check the account page or the broken-link case. See NEW‑1 and NEW‑2.

## Every finding from the first trial

| # | Finding (first trial) | Now | Evidence |
|---|---|---|---|
| 1 | Transcribe deleted everything I'd typed | **Closed** | Typed 147 chars in Q1 and 154 in Q3, saved, attached the photo, pressed Transcribe: both boxes byte-for-byte unchanged afterwards. The transcript lands in its own **From your photo** panel, not in my boxes. `18-before-transcribe-400.png`, `21-attachment-area-400.png` |
| 1b | Hand in stayed enabled while transcribing | **Closed** | Hand in is greyed and disabled for the ~4 s the spinner runs. `19-transcribing-400.png`, `20-after-transcribe-400.png` |
| 2 | The transcription isn't saved | **Closed** | Left the page, came back: the transcript panel is still there with its text and an **Insert** button, and it is still there after hand-in. `21-attachment-area-400.png`, `31-locked-photo-panel-400.png` |
| 3 | The homework PDF is unreadable on the phone | **Closed** | On the phone there is no squashed embed at all now — just **Open PDF** and **Download**. Open PDF fills the screen and I could read every question. The embed is still there at 1440, where it works. `06-hw1-top-400.png`, `07-open-pdf-tab-400.png`, `13-hw1-1440.png` |
| 4 | Questions full of dollar signs | **Closed** | "A uniform beam AB has length 3.0 m and weight 240 N…" — clean prose in all five. `06-hw1-full-400.png` |
| 5 | One Answers box for five questions | **Closed** | Five boxes, each under its own question, each labelled Q1…Q5, and they grow to fit what I type instead of scrolling inside. `14-answers-typed-400.png` |
| 6 | Attaching a photo throws you to the top | **Closed** | Scroll position was identical before and after picking the file (1674 px both times); the "Attached" tick appears where I am. `17-attached-400.png` |
| 7 | No preview of the photo I attached | **Closed** | A 320-px thumbnail of the photo, right there in the form, before and after hand-in. `17-attached-400.png` |
| 8 | Raw file picker, no camera | **Closed** | A proper **Add a photo** button with a camera icon; it asks for the camera first (`capture="environment"`) and accepts png/jpg/heic/webp/pdf. `16-photo-area-before-400.png` |
| 9 | Feedback filed under "Hi Leo," | **Closed** | The card is titled **Moments and Equilibrium Practice**, 17 Sept 2026. (Seen in the list at 17:07–17:10; I was deleted before I could open it.) |
| 10 | Nothing links the homework to its feedback | **Partly** | The feedback card now names the homework, so I could find it. But the marked homework page still has no link to the feedback — nothing on it mentions feedback at all. `33-marked-full-400.png` |
| 11 | Two different dates for the same deadline | **Still open** | Home and the homework page say **Due 24 Sept 2026**; the sheet itself says "to work through before your lesson on **Friday 18 September**"; my tutor's mark comments say "Bring the sheet on Friday". Three places, two deadlines. `03-home-400.png`, `07-open-pdf-tab-400.png`, `33-marked-full-400.png` |
| 12 | Nowhere does it say how I did | **Closed** — best fix in the release | A **Marks** card at the top of the homework: **5 / 20** in big type, then every question with its own mark (2/2, 0/5, 3/3, 0/3, 0/7) and a comment, then a summary. `33-marked-top-400.png`, `33-marked-full-400.png` |
| 13 | Home says "Nothing due right now" while work is outstanding | **Still open** | Handed in 17:03 → home immediately said "Nothing due right now — nice." Marked 17:06 → home still said "Nothing due right now" and "NEW FEEDBACK: Nothing yet". My 5/20 never reached the home screen. `29-home-after-handin-400.png` |
| 14 | "Handed in" / "Submitted" / "You handed this in" | **Partly** | Down to two: the list card says "Handed in 17 Sept 2026, 17:03" under a **HANDED IN** header but wears a **Submitted** chip; the detail page says "Submitted 17 Sept 2026, 17:03. Not marked yet." `30-list-after-handin-400.png`, `27-after-handin-400.png` |
| 15 | The Lessons page is one line | **Still open** | "Tomorrow, 17:00 / 1 hour / Scheduled". No tutor name, no subject, no place or link, no past lessons. `10-lessons-400.png` |
| 16 | Signed out mid-session, then my password stopped working | **Still open — it happened again** | At 17:11, mid-session, every `/me` page started redirecting to the tutor app; signing out and back in with the password I had used 40 minutes earlier gave "Could not sign in. Check the email and password." Still failing after nine attempts over 15 minutes. `34-unexpected_me-400.png`, `39-after-resignin-400.png` |
| 17 | No "forgot my password" anywhere | **Still open** | Email, Password, Sign in. Nothing else. `01-landing-400.png` |
| 18 | Signing in doesn't change the address bar | **Closed** | Sign in → `/me`; sign out → `/login`, both immediately. |
| 19 | The sign-in page is written to my tutor | **Still open** | "Of the stars — a quiet study for **your students** and their work." `01-landing-400.png` |
| S1 | Broken homework link takes 8 s to fail | **Not re-tested** | I was locked out before I got to it. |
| S2 | My whole name is in the First name box; I can edit my sign-in email | **Still open** | First name "Trial Student Leo", Last name empty, Email editable by me with no confirmation step. `11-account-400.png` |
| S3 | Hand-in dialog says "them" | **Closed** | "Hand this homework in? Your answers cannot be changed afterwards." `26-handin-confirm-400.png` |

Also still true, and still good: hand-in really locks (boxes and picker gone, survives reload —
`28-locked-after-reload-400.png`), drafts save and survive a reload, transcription is fast and
accurate (~4 s, both lines exactly right), and the marking read my *actual* answers rather than
flattering me — it spotted that my Q2 was a different question entirely and said so.

## New findings

### NEW‑1. My tutor deleted me and the app put me inside the tutor's app — High — `34-unexpected_me-400.png`, `35-tutor-view-menu-400.png`

At 17:11 I opened Feedback and landed on a page headed **Home** with "Upcoming sessions", "To
review — The desk is clear." and "Material", none of which ever loaded. The menu had changed to
**Home / Students / Library / Topics**, my name was replaced by the word "Signed in", and there
was an **Add student** button and an **Add material** button. `/me`, `/me/homework` and
`/me/feedback` all redirected to it. Nothing told me anything had changed.

Nothing of anyone else's showed — Students said "Could not load students." and the rest sat on
loading skeletons forever — so I don't think I *saw* anything I shouldn't. But a 17-year-old
being dropped into his tutor's admin screens, with buttons that offer to add students, is a
frightening thing to happen on its own, and the skeletons that never resolve make it look like
the app is broken rather than like something happened to my account.

### NEW‑2. Deleting a student while they are signed in tells them they typed their password wrong — High — `39-after-resignin-400.png`

I signed out of that state and signed back in with the password I had been using all afternoon:
"Could not sign in. Check the email and password." Nine attempts over 15 minutes, same. From my
seat I am locked out of an account I know the password to, and the app blames my typing. If my
account has been closed, say so — "this account has been closed, speak to your tutor" — because
with finding 17 still open there is no password reset to fall back on either.

Worse for me personally: my marks and my tutor's comments went with it. I read them once, at
17:06. Five minutes later there was no way back to them. Nothing warned me that the page I was
reading was about to become unreachable.

### NEW‑3. The questions in my answer boxes are not the questions on the sheet — Medium — `06-hw1-full-400.png` vs `07-open-pdf-tab-400.png`

Sheet Q2: "…at an angle of 30° to the beam. **(a)** Draw the line of action… **(b)** Calculate the
moment… **(c)** A classmate writes M = 50 × 2.0 = 100 N m. State what they have done wrong.
**[5 marks]**". On screen, Q2 is a single paraphrase with no parts and no mark count. So the box
labelled Q2 asks for one thing and the sheet asks for three, and I get marked out of 5 (0/5, as
it turned out) for a question the screen never showed me in full. Whichever is authoritative,
they should be the same words.

### NEW‑4. Nothing on screen says what each question is worth until after it's marked — Medium — `14-answers-typed-400.png`, `33-marked-top-400.png`

While I was answering, every box looked equally important. Afterwards I learn Q5 was worth 7
marks and Q1 was worth 2 — I spent my time the wrong way round. The marks exist in the system
before I hand in (the marking knew them), and they're printed on the sheet for one question.
Put "[7 marks]" next to the box.

### NEW‑5. **Insert** doesn't say which box it will fill, and with nothing focused it picks the last one — Medium — `22-insert-clicked-400.png`, `23-insert-into-q2-400.png`

The Insert button sits in the transcript panel below Q5, a long scroll from Q1. I pressed it
without touching a box first and the text silently went into **Q5**, which is not where that
working belonged; nothing on screen changed, because Q5's box was off the top of the viewport.
Tapping into Q2 first and pressing Insert put it into Q2 — so it follows the last box I touched,
which is a reasonable rule that nothing tells me about. The button should say "Insert into Q2",
or each box should have its own insert.

### NEW‑6. "Clear" next to "Insert" reads like a button that throws the transcription away — Low — `21-attachment-area-400.png`

The transcript panel header is: *From your photo* · **Clear** · **Insert**. "Clear" is actually a
green badge meaning my handwriting came out legible. Sat beside a real verb button, on a feature
that used to destroy my typing, I read it as "Clear this" and did not dare press it. Call it
"Legible" or "Read clearly".

### NEW‑7. Handing in with blank questions raises nothing — Low — `26-handin-confirm-400.png`

I handed in with Q4 and Q5 empty and got the normal "Hand this homework in?" dialog. Ten of the
twenty marks were sitting in those two boxes. "You have not answered Q4 and Q5 — hand in anyway?"
would have cost me nothing and saved me 10 marks.

### NEW‑8. The marks list repeats the question and hides my answer — Low — `33-marked-top-400.png`

Each row in the Marks card is the question text, truncated with "…", then the mark, then the
comment. To see what I actually wrote for Q2 I had to scroll past the whole Marks card and find
Q2 again further down. The one thing I want beside "0 / 5" is my own answer.

---

The app is much better than it was a week ago: the thing that used to eat my work now sits in
its own panel and leaves my typing alone, the sheet is readable on a phone, each question has
its own box, and for the first time I can see that I got 5 out of 20 and exactly why.

What I cannot get past is that halfway through reading those marks the app moved me into my
tutor's admin screens and then told me my own password was wrong — my work, my marks and my
feedback vanished mid-sentence and the app never once said what had happened.
