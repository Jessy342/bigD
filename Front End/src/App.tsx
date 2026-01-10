import { Toaster } from "sonner";
import { GameBoard } from "./components/GameBoard";

export default function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0a0e27] via-[#1a1f3a] to-[#0a0e27] flex items-center justify-center p-4">
      {/* Animated background particles */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-2 h-2 bg-primary/30 rounded-full animate-pulse" />
        <div className="absolute top-3/4 left-3/4 w-2 h-2 bg-primary/30 rounded-full animate-pulse delay-100" />
        <div className="absolute top-1/2 right-1/4 w-1 h-1 bg-primary/20 rounded-full animate-pulse delay-200" />
      </div>

      <div className="relative z-10 w-full max-w-2xl">
        <GameBoard />
      </div>
      <Toaster position="top-center" richColors />
    </div>
  );
}
