import { Toaster } from "sonner";
import { GameBoard } from "./components/GameBoard";

export default function App() {
  return (
    <div className="min-h-screen">
      <div className="relative z-10 w-full">
        <GameBoard />
      </div>
      <Toaster position="top-center" richColors />
    </div>
  );
}
