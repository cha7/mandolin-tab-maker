import TabMaker from "./TabMaker";
import styles from "./page.module.css";

export default function Home() {
  return (
    <main className="fh-container fh-stack">
      <p className={`fh-muted ${styles.intro}`}>
        Paste a YouTube link. The melody is pulled out and arranged for mandolin (GDAE); sections
        it isn&apos;t confident about are hidden unless you ask for them.
      </p>
      <TabMaker />
    </main>
  );
}
