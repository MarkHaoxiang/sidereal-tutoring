# Student trial — Leo, 17, A-level physics

Trialled 17 Sept 2026 on a 400×850 phone screen first, then the same screens at 1440×900.
Account: Trial Student Leo. Screenshots are in `.screenshots/trial-student/`.

## What I did

Signed in, found the homework, read the PDF, typed answers to Q1 and Q3, attached a photo of
handwritten working, ran Transcribe, corrected a unit, handed in, tried to change my answer
afterwards, checked feedback / plan / lessons, changed the theme and my password, signed out
and back in, then waited for the tutor to mark it.

## The big one

### 1. Transcribe deleted everything I'd typed — Critical — `13-transcribing-400.png`, `14-after-transcribe-400.png`

Steps: type answers into the Answers box → Save draft ("Saved") → attach a photo → press
Transcribe. About 5 seconds later the whole box is replaced by the two lines from the photo.
My 434 characters of Q1 and Q3 working were gone. No warning before, no undo after, nothing
that says "this will replace what's in the box". The only hint anything is about to happen is
a spinner inside the button.

If I'd pressed Hand in at that point — and I nearly did, because Hand in stays enabled the
whole time, including while it's still transcribing — I'd have submitted two lines instead of
an hour's work, and I can't change it afterwards.

### 2. The transcription isn't saved — High — (no screenshot; it's an absence)

After Transcribe I navigated away and came back. The box had my *old saved draft* in it, not
the transcript. So the transcription only ever existed on screen: leave the page, lose it, and
the only way to get it back is to press Transcribe again. That's the opposite way round from
what I'd expect — the expensive bit is the thing it throws away, and the thing it throws away
is the thing it just overwrote my work with.

## Phone problems

### 3. The homework PDF is unreadable on the phone — High — `07-hw-viewport-top-400.png`

The PDF sits in a box about 334×510 points, and ~55 of that is the browser's own PDF toolbar.
An A4 page squeezed into that is a grey blur — I could make out the title and nothing else.
The questions are printed again as text underneath (see #4), so the PDF is effectively
decoration on a phone until you tap out of it.

Tapping **Open PDF** does work and is readable full screen (`08-open-pdf-tab-400.png`), and
**Download** gave me a proper 37 KB `moments-and-equilibrium.pdf`. Both good. But the default
state — the thing I see first — is useless, and nothing tells me to tap Open PDF.

At 1440×900 the same embed is perfectly readable (`44-homework-detail-1440.png`). This is a
phone-only problem.

### 4. The questions underneath the PDF are full of dollar signs — Medium — `06-homework-detail-400.png`

"A uniform plank $A B$ has length $4.0$ m and weight $150$ N… at an angle of $30°$ to the beam."
Every variable and number is wrapped in `$`. It's the whole sheet, all five questions, and it's
the only readable copy on a phone. It reads like something broke.

### 5. One Answers box for five questions — Medium — `09-answers-typed-400.png`

There is a single box labelled "Answers" for the entire sheet. Five questions with (a)(b)(c)
parts each, and I have to type "Q1 (a)…" myself and keep track of my own numbering. The box is
a fixed ~265pt tall and doesn't grow, so once you're past about eight lines you're typing into
a little scrolling window on a phone and can't see what you wrote earlier.

### 6. Attaching a photo throws you back to the top of the page — Low — `11-file-attached-400.png`

Pick the file, and the page jumps to the top while the "Attached" confirmation appears right at
the bottom, off screen. On a page this long that's a lot of scrolling to get back to where I was.

### 7. No preview of the photo I attached — Low — `12-attachment-area-400.png`

All I get is the filename. I can't see whether the photo I just took is the right page, the
right way up, or too blurry to read — and after hand-in I can't change it. There's a link on
the filename, but tapping it means leaving the form.

### 8. The file picker is the raw browser one and doesn't offer the camera — Low — `09-answers-typed-400.png`

"Choose file / No file chosen", unstyled, next to everything else which is nicely designed. On
a phone the obvious thing to do is take a photo of my page, and it opens the file browser.

## Things that didn't add up

### 9. Feedback is filed under "Hi Leo," — Medium — `50-feedback-list-400.png`

The Feedback list shows one card titled **"Hi Leo,"** with the date. That's the first line of
the letter being used as the title. Every piece of feedback I ever get will be called "Hi Leo,".
Nothing on the card or inside says which homework it's about — I had to work that out from the
content.

### 10. Nothing links the homework to its feedback — Medium — `54-homework-after-feedback-400.png`

After marking, the homework page says "You handed this in on 17 Sept 2026, 14:55. Marked by your
tutor." and stops there. No link to the feedback, no extract, nothing. I had to go to the menu,
tap Feedback, and open "Hi Leo,". Going the other way is the same — the feedback doesn't link
back to the homework or the PDF.

### 11. The app tells me two different dates for the same lesson — Medium — `51-feedback-detail-400.png`, `23-lessons-400.png`

Feedback: "**Two things to do before Tuesday**". Home and Lessons: "**Tomorrow, 17:00** · 1 hour",
which on 17 Sept is Friday. So do I have until tomorrow or until Tuesday? Those are the two most
important facts on the screen and they disagree.

### 12. Nowhere does it say how I did — Medium — `54-homework-after-feedback-400.png`

The chip says "Marked", the letter is encouraging, and there is no mark, score, or "3 of 5
questions attempted" anywhere. The sheet itself is printed with [2 marks], [3 marks], [4 marks]
next to every part, so the marks clearly exist somewhere — I just don't get to see them.

### 13. Home says "Nothing due right now — nice." while my homework is sitting unmarked — Low — `20-home-after-handin-400.png`

Once it's handed in it vanishes off the home screen entirely. It's neither in Due Soon nor
anywhere else until feedback appears. For an hour I had no evidence on the home screen that I'd
done anything at all.

### 14. "Handed in", "Submitted" and "You handed this in" are three names for one thing — Low — `19-homework-list-after-400.png`, `27-homework-dark-400.png`

The list section header says HANDED IN, the chip on the same card says Submitted, the detail page
chip says Submitted and the sentence says "You handed this in".

### 15. The Lessons page is one line — Low — `47-lessons-1440.png`

"Tomorrow, 17:00 · 1 hour · Scheduled". No tutor name, no subject or topic, no address or video
link, and no past lessons. It's one of five things in the menu and there's nothing in it.

## Signing in and out

### 16. I got signed out mid-session with no explanation, and then my password stopped working — Medium — `59-session-expired-1440.png`, `60-resignin-attempt.png`

I'd been reading feedback, clicked through to the home page, and landed on the sign-in screen.
No "your session has expired", no message at all — just the login page, and I'd lost my place.

Then my password (which I'd changed 25 minutes earlier and successfully signed in with) was
rejected: "Could not sign in. Check the email and password." My old password was rejected too.
I waited three minutes and tried again — same. So from my seat I am locked out of my own account
with a password I know is right, and the app's only message is that I've probably mistyped it.

*(It's possible someone deactivated the trial account at the far end while I was still in it. If
so, that's the same problem wearing a different hat: I get a generic "check your password"
either way.)*

### 17. There is no "forgot my password" anywhere — Medium — `01-landing-400.png`

Sign-in page is Email, Password, Sign in. That's it. Given #16, this is the bit where a real 17
year old texts his tutor.

### 18. Signing in doesn't change the address bar — Low

After Sign in, the content switches to my homework but the URL still says `/login` until I
navigate somewhere. Same after Sign out — content is the login page, URL still `/me/account`.
Reloading right after signing in bounces you around.

### 19. The sign-in page is written to my tutor, not to me — Low — `01-landing-400.png`

"Of the stars — a quiet study for **your students** and their work." I'm the student.

## Small stuff

- **Broken homework link takes 8 seconds to say so** — Low — `37-bogus-homework-id-400.png`. An
  old link shows "Loading…" for ~8 s, then "Could not load this homework." with no way back
  except the top menu.
- **My name is all in the First name box** — Low — `24-account-400.png`. "First name: Trial
  Student Leo", Last name empty. Also I can edit the email I sign in with, freely, on my own.
- **The hand-in dialog says "them" with nothing to point at** — Low — `16-handin-confirm-400.png`.
  "Hand this homework in? You will not be able to change **them** afterwards."

## What actually worked

- **Hand-in really does lock.** After confirming, the box and the file picker are gone — not
  disabled, gone (`18-locked-after-handin-400.png`). I reloaded, went back in from the list,
  came at it from the home screen: no way in. Good. The confirmation dialog before it is clear
  and "Not yet" is the right words.
- **Transcription was accurate and fast.** 5.4 seconds, and it got both lines of my messy
  handwriting exactly right including the numbers. That part is genuinely impressive — which is
  what makes #1 and #2 so annoying.
- **Dark mode is properly done** (`26-home-dark-400.png`, `27-homework-dark-400.png`) and it
  stuck across sign-out and sign-in. The moon toggle is in the menu as well as in Account.
- **Password change errors are the best copy in the app.** "That is not your current password."
  "These two do not match." Both appear right under the field that's wrong
  (`28-pw-wrong-current-400.png`, `29-pw-mismatch-400.png`).
- **Draft saving works and survives a reload.** Typed text came back intact.
- **The PDF has my name on it** ("Student: Trial Student Leo") and the download is a real file
  I could put in a folder.
- **I couldn't see anything I shouldn't.** I tried a made-up homework id in the URL and got
  refused, not shown someone else's sheet. Every page I reached was mine. The only other person
  who appears anywhere is "your tutor", unnamed.

## Did the homework make sense?

Yes, and it was better than the sheets I usually get. It builds: plank on two supports, then the
same plank with someone walking along it until it tips, then an angled force, then a non-uniform
bar, then a hinged rod with a cable. The paragraph at the top ("state clearly which point you are
taking moments about before you write the equation — this is where marks are usually lost") is the
thing my teacher says every lesson, and it's right there where I'd read it. Ruled answer lines
printed under each question, so it's a sheet I could actually print and write on.

One odd one: Q4(b) asks "State one reason marks are commonly lost in this type of question, and
how you would avoid it. [1 mark]". That's not a physics question, it's a revision prompt with a
mark attached, and I didn't know whether I was supposed to answer it in the box or just think it.

## Did the feedback make sense?

Yes — this is the best thing in the app. `51-feedback-detail-400.png`. It's addressed to me, it
says what was right ("Q1 and Q3 are both correct – solid, clean work on those"), what was missing
(Q2, Q4, Q5 blank — correct, it noticed), and then two specific things to do, ending with "Redo Q2
first, explicitly writing 'taking moments about [point]' before you start". That's an instruction I
can follow on a Sunday night without asking anyone anything. It doesn't talk down to me and it
doesn't pad.

Two nits. It says "Two things to do before Tuesday" and then gives two numbered things plus a
"Next step", which is three. And it credits me for "extra working on the photo you attached… good
practice for showing your method" — the photo was moments working for a question that isn't on this
sheet, so that praise is generous to the point of being made up. If it's going to comment on my
photo it needs to have actually looked at what's in it.

---

Would I rather have this than WhatsApp a photo to my tutor? Yes — because the feedback came back
written down, in order, with "do this first" at the end, instead of scrolling back through voice
notes and blurry photos to find the bit where he told me what to fix.

But not on my phone yet — the PDF is unreadable at that size, five questions share one text box,
and the button that types up my handwriting silently deleted everything I'd already written, which
is the one thing WhatsApp has never done to me.
