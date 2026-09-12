import { LogOut } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";

export function SignOutButton() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  const signOut = async () => {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      setSigningOut(false);
      void navigate("/login", { replace: true });
    }
  };

  return (
    <Button
      loading={signingOut}
      onClick={() => {
        void signOut();
      }}
    >
      <LogOut size={15} aria-hidden="true" />
      Sign out
    </Button>
  );
}
