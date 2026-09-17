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
      <h1 className={styles.heading}>Your account</h1>

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
