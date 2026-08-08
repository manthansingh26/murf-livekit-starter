import { Button } from '@/components/ui/button';

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
  micError?: string;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  micError,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div ref={ref} className="min-h-screen w-full bg-slate-50 text-slate-900 overflow-x-hidden selection:bg-teal-200 selection:text-teal-900 flex flex-col">
      
      {/* Navbar */}
      <nav className="w-full flex items-center justify-between px-6 lg:px-16 py-5 border-b border-slate-100 bg-white/80 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-teal-600 flex items-center justify-center text-white font-extrabold text-lg shadow-sm">
            S
          </div>
          <span className="font-bold text-lg tracking-tight text-slate-800">Saathi Swasthya</span>
        </div>
        <div className="hidden sm:flex items-center gap-4 text-sm font-medium text-slate-500">
          <span className="px-3 py-1 bg-slate-100 rounded-full border border-slate-200 text-xs font-semibold text-slate-600">
            English | हिन्दी | ગુજરાતી
          </span>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="flex-1 flex flex-col lg:flex-row items-center max-w-6xl mx-auto w-full px-6 lg:px-16 py-16 lg:py-24 gap-12 lg:gap-20">
        
        {/* Left: Value Proposition */}
        <section className="w-full lg:w-1/2 flex flex-col items-start text-left gap-6">
          
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-teal-50 border border-teal-100 text-teal-700 text-xs font-semibold">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-500"></span>
            </span>
            Voice AI Beta
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-slate-900 leading-[1.1]">
            Your personal{' '}
            <span className="text-teal-600">health navigator.</span>
          </h1>

          <p className="text-base sm:text-lg text-slate-600 leading-relaxed max-w-lg">
            Speak naturally about your symptoms. Saathi will listen, understand, and guide you — in English, Hindi, or Gujarati.
          </p>

          {micError && (
            <div className="w-full max-w-lg flex gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-left items-start">
              <span className="text-red-500 text-lg leading-none mt-0.5">🛑</span>
              <p className="text-sm text-red-800 leading-relaxed font-medium">
                {micError}
              </p>
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto pt-2">
            <Button
              size="lg"
              onClick={onStartCall}
              className="w-full sm:w-auto h-12 px-8 rounded-xl bg-teal-600 hover:bg-teal-700 active:scale-[0.98] text-white font-semibold text-base shadow-sm transition-all duration-150"
            >
              🎙️ {startButtonText}
            </Button>
          </div>

          {/* Medical Disclaimer */}
          <div className="w-full max-w-lg flex gap-3 p-4 bg-amber-50 border border-amber-100 rounded-xl text-left items-start mt-2">
            <span className="text-amber-500 text-lg leading-none mt-0.5">⚠️</span>
            <p className="text-xs text-amber-700 leading-relaxed">
              Saathi is an AI triage assistant. It does not diagnose or prescribe.{' '}
              <strong className="text-amber-800">For emergencies, call 112.</strong>
            </p>
          </div>
        </section>

        {/* Right: Chat Mockup */}
        <section className="w-full lg:w-1/2 flex items-center justify-center">
          <div className="w-full max-w-sm bg-slate-900 rounded-3xl shadow-xl p-6 space-y-4">
            <div className="flex items-center gap-3 pb-3 border-b border-slate-700">
              <div className="w-10 h-10 bg-teal-600 rounded-xl flex items-center justify-center text-white font-bold">S</div>
              <div>
                <div className="text-white font-semibold text-sm">Saathi Assistant</div>
                <div className="text-teal-400 text-xs flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse"></span> Online
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <div className="bg-slate-800 rounded-2xl rounded-tl-sm p-3 text-slate-200 text-sm w-[90%]">
                Namaste! How are you feeling today?
              </div>
              <div className="bg-teal-600 rounded-2xl rounded-tr-sm p-3 text-white text-sm w-[80%] ml-auto">
                I've had a mild fever since yesterday.
              </div>
              <div className="bg-slate-800 rounded-2xl rounded-tl-sm p-3 text-slate-200 text-sm w-[95%]">
                I'm sorry to hear that. How high has the temperature been?
              </div>
            </div>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="w-full text-center py-5 text-slate-400 text-xs border-t border-slate-100">
        &copy; {new Date().getFullYear()} Saathi Swasthya · Built for the Murf AI Voice Agents Challenge
      </footer>
    </div>
  );
};
