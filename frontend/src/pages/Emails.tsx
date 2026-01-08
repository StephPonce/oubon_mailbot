// 
// EMAILS - Automation & Support (Placeholder)
// AI-powered email responses and automation rules
// 

import { Mail, Construction } from 'lucide-react';

export default function Emails() {
  return (
    <div className="animate-fade-in">
      <div className="glass-card-static p-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 flex items-center justify-center mx-auto mb-4">
          <Mail className="w-8 h-8 text-cyan-400" />
        </div>
        <h1 className="text-xl font-semibold text-white mb-2">Emails</h1>
        <p className="text-white/60 text-sm max-w-md mx-auto mb-6">
          AI-powered customer support, smart automation rules, and operating hours management.
        </p>
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500/10 text-amber-400 text-sm">
          <Construction className="w-4 h-4" />
          Coming Soon
        </div>
      </div>
    </div>
  );
}
