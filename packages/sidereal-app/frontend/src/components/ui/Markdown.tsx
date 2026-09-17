import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { markUnreadable } from "@/lib/transcription";

const PLAIN = [remarkGfm];
const TRANSCRIBED = [remarkGfm, markUnreadable];

export interface MarkdownProps {
  children: string;
  /** Transcribed handwriting: the `[?]` spans it could not read are marked. */
  transcribed?: boolean;
}

export function Markdown({ children, transcribed = false }: MarkdownProps) {
  return (
    <div className="prose">
      <ReactMarkdown remarkPlugins={transcribed ? TRANSCRIBED : PLAIN}>{children}</ReactMarkdown>
    </div>
  );
}
