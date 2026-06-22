import { useEffect } from "react";
import MainLayout from "./components/layout/MainLayout";
import { useAppStore } from "./stores/appStore";

function App() {
  const { isDark, toggleTheme } = useAppStore();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.classList.toggle("light", !isDark);
  }, [isDark]);

  return (
    <div className={isDark ? "dark" : "light"}>
      <MainLayout isDark={isDark} toggleTheme={toggleTheme} />
    </div>
  );
}

export default App;
