import { AppearanceCard } from "@/components/account/AppearanceCard";
import { PasswordCard } from "@/components/account/PasswordCard";
import { ProfileCard } from "@/components/account/ProfileCard";
import { SignOutButton } from "@/components/account/SignOutButton";
import { PageHeader } from "@/components/ui";

import pageStyles from "./page.module.css";
import styles from "./AccountPage.module.css";

export function AccountPage() {
  return (
    <div>
      <PageHeader title="Your account" />

      <div className={pageStyles.stack}>
        <ProfileCard />
        <AppearanceCard />
        <PasswordCard />
        <div className={styles.signOut}>
          <SignOutButton />
        </div>
      </div>
    </div>
  );
}
