import { Monitor, Moon, Sun } from "lucide-react";

import { Card } from "@/components/ui";
import { cx } from "@/lib/cx";
import { useAppearance } from "@/lib/theme";
import type { Appearance } from "@/lib/theme";

import styles from "./account.module.css";

const CHOICES: { value: Appearance; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "auto", label: "System", Icon: Monitor },
];

export function AppearanceCard() {
  const [appearance, choose] = useAppearance();

  return (
    <Card title="Appearance">
      <fieldset className={styles.appearance}>
        <legend className={styles.visuallyHidden}>Theme</legend>
        <div className={styles.segments}>
          {CHOICES.map(({ value, label, Icon }) => (
            <label key={value} className={cx(styles.segment, appearance === value && styles.segmentOn)}>
              <input
                type="radio"
                name="appearance"
                value={value}
                checked={appearance === value}
                className={styles.segmentInput}
                onChange={() => {
                  choose(value);
                }}
              />
              <Icon size={15} aria-hidden="true" />
              {label}
            </label>
          ))}
        </div>
        <p className={styles.hint}>System follows your device. Saved to your account.</p>
      </fieldset>
    </Card>
  );
}
