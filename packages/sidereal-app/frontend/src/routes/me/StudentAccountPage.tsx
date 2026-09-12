import { AboutYouCard } from "@/components/account/AboutYouCard";
import { AppearanceCard } from "@/components/account/AppearanceCard";
import { PasswordCard } from "@/components/account/PasswordCard";
import { ProfileCard } from "@/components/account/ProfileCard";
import { SignOutButton } from "@/components/account/SignOutButton";

import accountStyles from "../AccountPage.module.css";
import styles from "./me.module.css";

export function StudentAccountPage() {
  return (
    <div className={styles.stack}>
      <div>
        <h1 className={styles.heading}>Your account</h1>
        <p className={styles.subheading}>Your name and photo, how the app looks, and your password.</p>
      </div>

      <ProfileCard />
      <AppearanceCard />
      <PasswordCard />
      <AboutYouCard />

      <div className={accountStyles.signOut}>
        <SignOutButton />
      </div>
    </div>
  );
}
