import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  // The generated client is regenerated wholesale by `npm run gen-api`, so any fix
  // here would be undone on the next run.
  { ignores: ["dist", "src/lib/api-schema.d.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      globals: globals.browser,
      // projectService rather than a `project` list: it picks the right tsconfig per
      // file, so `vite.config.ts` is checked under tsconfig.node.json without a
      // second block here.
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  // `recommended-latest` is the flat-config spelling of `recommended`; the plain key
  // is still eslintrc-shaped and flat config rejects its string-array `plugins`.
  //
  // The plugin is pinned to 5.x on purpose. From 6.x its `recommended` also turns on
  // the React Compiler rule set, which this app has not adopted — it is React 18 with
  // no compiler. Adopting those rules is its own decision, not a lint config edit.
  reactHooks.configs["recommended-latest"],
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-refresh": reactRefresh },
    rules: {
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  }
);
