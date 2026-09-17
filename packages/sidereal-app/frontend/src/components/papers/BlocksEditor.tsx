import { Plus } from "lucide-react";

import { Button, Field, Input, Select, Textarea } from "@/components/ui";
import { assetFileId, useFileBlob } from "@/lib/files";

import { EditorTools } from "./EditorTools";
import { BLOCK_KINDS, MAX_FIGURE_WIDTH_MM, emptyBlock, moved } from "./draft";
import type { BlockDraft, PassageDraft } from "./draft";
import styles from "./papers.module.css";

export interface BlocksEditorProps {
  blocks: BlockDraft[];
  /** The paper's passages, so a reference is chosen rather than typed. */
  passages: PassageDraft[];
  /** What the node is called, for the controls' labels: "question 3". */
  label: string;
  onChange: (blocks: BlockDraft[]) => void;
}

function Figure({ asset, label }: { asset: string; label: string }) {
  const file = useFileBlob(assetFileId(asset), asset);

  if (!asset.trim()) {
    return null;
  }
  if (file.error !== null || assetFileId(asset) === null) {
    return <p className={styles.blockNote}>That image could not be opened.</p>;
  }
  if (file.url === null) {
    return <p className={styles.blockNote}>Loading the image…</p>;
  }
  return <img className={styles.blockImage} src={file.url} alt={label} />;
}

function TableRows({
  block,
  label,
  onChange,
}: {
  block: Extract<BlockDraft, { type: "table" }>;
  label: string;
  onChange: (next: BlockDraft) => void;
}) {
  const columns = block.header?.length ?? block.rows[0]?.length ?? 0;
  const blank = (count: number) => Array.from({ length: count }, () => "");

  const setCell = (rowIndex: number, cellIndex: number, value: string) => {
    onChange({
      ...block,
      rows: block.rows.map((row, position) =>
        position === rowIndex
          ? row.map((cell, index) => (index === cellIndex ? value : cell))
          : row
      ),
    });
  };

  return (
    <div className={styles.grid}>
      <table className={styles.gridTable}>
        {block.header !== null ? (
          <thead>
            <tr>
              {block.header.map((cell, index) => (
                <th key={index}>
                  <Input
                    value={cell}
                    aria-label={`${label} column ${String(index + 1)} name`}
                    onChange={(event) => {
                      onChange({
                        ...block,
                        header: (block.header ?? []).map((entry, position) =>
                          position === index ? event.target.value : entry
                        ),
                      });
                    }}
                  />
                </th>
              ))}
              <th />
            </tr>
          </thead>
        ) : null}
        <tbody>
          {block.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>
                  <Input
                    value={cell}
                    aria-label={`${label} row ${String(rowIndex + 1)} cell ${String(cellIndex + 1)}`}
                    onChange={(event) => {
                      setCell(rowIndex, cellIndex, event.target.value);
                    }}
                  />
                </td>
              ))}
              <td>
                <EditorTools
                  label={`${label} row ${String(rowIndex + 1)}`}
                  index={rowIndex}
                  count={block.rows.length}
                  onMove={(delta) => {
                    onChange({ ...block, rows: moved(block.rows, rowIndex, delta) });
                  }}
                  onRemove={() => {
                    onChange({
                      ...block,
                      rows: block.rows.filter((_, position) => position !== rowIndex),
                    });
                  }}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className={styles.addRow}>
        <Button
          size="sm"
          onClick={() => {
            onChange({ ...block, rows: [...block.rows, blank(columns || 1)] });
          }}
        >
          <Plus size={14} aria-hidden="true" />
          Row
        </Button>
        <Button
          size="sm"
          onClick={() => {
            onChange({
              ...block,
              header: block.header === null ? null : [...block.header, ""],
              rows: block.rows.map((row) => [...row, ""]),
            });
          }}
        >
          <Plus size={14} aria-hidden="true" />
          Column
        </Button>
        <Button
          size="sm"
          onClick={() => {
            onChange({ ...block, header: block.header === null ? blank(columns || 1) : null });
          }}
        >
          {block.header === null ? "Add a header row" : "Drop the header row"}
        </Button>
      </div>
    </div>
  );
}

function BlockBody({
  block,
  passages,
  label,
  onChange,
}: {
  block: BlockDraft;
  passages: PassageDraft[];
  label: string;
  onChange: (next: BlockDraft) => void;
}) {
  switch (block.type) {
    case "passage":
      return (
        <>
          <Field label="Title">
            <Input
              value={block.title}
              aria-label={`${label} title`}
              onChange={(event) => {
                onChange({ ...block, title: event.target.value });
              }}
            />
          </Field>
          <Field label="Text" help="Set line for line, exactly as it is typed.">
            <Textarea
              rows={5}
              value={block.text}
              aria-label={`${label} text`}
              onChange={(event) => {
                onChange({ ...block, text: event.target.value });
              }}
            />
          </Field>
        </>
      );
    case "passage_ref":
      return (
        <Field label="Passage">
          <Select
            value={block.id}
            aria-label={`${label} passage`}
            onChange={(event) => {
              onChange({ ...block, id: event.target.value });
            }}
          >
            <option value="">Choose a passage</option>
            {passages.map((passage) => (
              <option key={passage.key} value={passage.id}>
                {passage.title.trim() || passage.id || "Untitled"}
              </option>
            ))}
            {block.id && !passages.some((passage) => passage.id === block.id) ? (
              <option value={block.id}>{block.id} — not on this paper</option>
            ) : null}
          </Select>
        </Field>
      );
    case "code":
      return (
        <>
          <Field label="Language" className={styles.narrow}>
            <Input
              value={block.language}
              placeholder="python"
              aria-label={`${label} language`}
              onChange={(event) => {
                onChange({ ...block, language: event.target.value });
              }}
            />
          </Field>
          <Field label="Code">
            <Textarea
              rows={5}
              value={block.text}
              aria-label={`${label} code`}
              onChange={(event) => {
                onChange({ ...block, text: event.target.value });
              }}
            />
          </Field>
        </>
      );
    case "table":
      return (
        <>
          <Field label="Caption">
            <Input
              value={block.caption}
              aria-label={`${label} caption`}
              onChange={(event) => {
                onChange({ ...block, caption: event.target.value });
              }}
            />
          </Field>
          <TableRows block={block} label={label} onChange={onChange} />
        </>
      );
    case "figure":
      return (
        <>
          <Figure asset={block.asset} label={block.caption || label} />
          <Field label="Image" help="The file this figure draws, named as it was uploaded.">
            <Input
              value={block.asset}
              aria-label={`${label} image`}
              onChange={(event) => {
                onChange({ ...block, asset: event.target.value });
              }}
            />
          </Field>
          <div className={styles.numbers}>
            <Field label="Caption">
              <Input
                value={block.caption}
                aria-label={`${label} caption`}
                onChange={(event) => {
                  onChange({ ...block, caption: event.target.value });
                }}
              />
            </Field>
            <Field label="Width (mm)">
              <Input
                type="number"
                min={0}
                max={MAX_FIGURE_WIDTH_MM}
                step={1}
                value={block.widthMm}
                aria-label={`${label} width`}
                onChange={(event) => {
                  onChange({ ...block, widthMm: event.target.value });
                }}
              />
            </Field>
          </div>
        </>
      );
  }
}

/** What is set between a question's words and its parts: passages, code, tables, figures. */
export function BlocksEditor({ blocks, passages, label, onChange }: BlocksEditorProps) {
  return (
    <div className={styles.blocks}>
      {blocks.map((block, index) => {
        const kind = BLOCK_KINDS.find((entry) => entry.id === block.type);
        const name = `${label} ${kind?.label.toLowerCase() ?? block.type}`;
        return (
          <div key={block.key} className={styles.block}>
            <div className={styles.blockHeader}>
              <p className={styles.blockKind}>{kind?.label ?? block.type}</p>
              <EditorTools
                label={name}
                index={index}
                count={blocks.length}
                onMove={(delta) => {
                  onChange(moved(blocks, index, delta));
                }}
                onRemove={() => {
                  onChange(blocks.filter((_, position) => position !== index));
                }}
              />
            </div>
            <BlockBody
              block={block}
              passages={passages}
              label={name}
              onChange={(next) => {
                onChange(blocks.map((entry, position) => (position === index ? next : entry)));
              }}
            />
          </div>
        );
      })}

      <div className={styles.addRow}>
        <p className={styles.blockKind}>Add</p>
        {BLOCK_KINDS.map((kind) => (
          <Button
            key={kind.id}
            size="sm"
            onClick={() => {
              onChange([...blocks, emptyBlock(kind.id)]);
            }}
          >
            {kind.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
