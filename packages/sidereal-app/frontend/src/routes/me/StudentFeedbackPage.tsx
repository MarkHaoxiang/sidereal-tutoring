import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { Card, Markdown, Spinner } from "@/components/ui";
import { feedbackHomework, feedbackTitle } from "@/lib/feedback";
import { formatDate } from "@/lib/format";
import { useMyFeedback } from "@/lib/queries";

import styles from "./me.module.css";

export function StudentFeedbackPage() {
  const { id } = useParams<{ id: string }>();
  const { data: feedback, isLoading, isError } = useMyFeedback(id);
  const about = feedback ? feedbackHomework(feedback.homework) : null;

  return (
    <div className={styles.stack}>
      <div>
        <Link to="/me/feedback" className={styles.back}>
          <ArrowLeft size={14} aria-hidden="true" /> Feedback
        </Link>
        <h1 className={styles.heading}>{feedback ? feedbackTitle(feedback) : "Feedback"}</h1>
        {feedback ? <p className={styles.subheading}>{formatDate(feedback.date_created)}</p> : null}
        {about ? (
          <p className={styles.line}>
            <Link to={`/me/homework/${about.id}`} className={styles.feedbackLink}>
              Your homework
            </Link>
          </p>
        ) : null}
      </div>

      {isLoading ? (
        <p className={styles.loading}>
          <Spinner /> Loading…
        </p>
      ) : null}
      {isError ? <p className={styles.status}>Could not load this feedback.</p> : null}

      {feedback?.content ? (
        <Card>
          <Markdown>{feedback.content}</Markdown>
        </Card>
      ) : null}
    </div>
  );
}
