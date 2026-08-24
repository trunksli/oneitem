"use client";

import { useState, useEffect } from 'react';
import { MessageSquare, X, Send } from 'lucide-react';

const API_BASE = "http://localhost:8000";

export default function Home() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [comments, setComments] = useState<any[]>([]);
  const [newComment, setNewComment] = useState("");
  
  const [hourlyOne, setHourlyOne] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch Hourly One
    fetch(`${API_BASE}/hourly`)
      .then(res => res.json())
      .then(data => {
        setHourlyOne(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });

    // Fetch initial comments
    fetchComments();
    
    // Poll for new comments every 10s
    const interval = setInterval(fetchComments, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchComments = () => {
    fetch(`${API_BASE}/comments`)
      .then(res => res.json())
      .then(data => setComments(data))
      .catch(err => console.error(err));
  };

  const handleSendComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    
    const commentText = newComment;
    setNewComment("");
    
    try {
      const res = await fetch(`${API_BASE}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: commentText })
      });
      if (res.ok) {
        fetchComments();
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading ONE...</div>;
  }

  // Fallback if DB is empty
  const candidate = hourlyOne?.candidate || {
    title: "We are discovering something amazing...",
    creator_name: "ONE Engine",
    source_type: "System",
    ai_explanation: "Check back shortly when the AI selects the next diamond.",
    thumbnail_url: ""
  };
  const theme = hourlyOne?.hourly?.theme || "Random";

  return (
    <main className="min-h-screen bg-[#FDFDFD] text-[#111111] font-sans flex flex-col items-center justify-center p-6 md:p-24 selection:bg-black selection:text-white relative overflow-hidden">
      
      {/* Header */}
      <header className="absolute top-0 w-full p-8 flex justify-between items-center z-10">
        <div className="flex flex-col">
           <h1 className="text-xl font-bold tracking-tighter">ONE</h1>
           <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">{theme} Hour</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-sm font-medium tracking-wide text-gray-500 uppercase hidden sm:block">
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
          </div>
          <button 
            onClick={() => setIsChatOpen(true)}
            className="flex items-center gap-2 text-sm font-bold tracking-widest uppercase hover:text-gray-500 transition-colors"
          >
            <MessageSquare size={18} />
            <span>Chat ({comments.length})</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className={`max-w-4xl w-full flex flex-col items-center gap-12 mt-16 transition-all duration-500 ${isChatOpen ? 'md:-translate-x-48 opacity-50 md:opacity-100' : ''}`}>
        
        <div className="text-center space-y-4">
          <p className="text-sm tracking-widest uppercase text-gray-400">Current Feature</p>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-medium tracking-tight leading-tight max-w-3xl">
            {candidate.title}
          </h2>
          <div className="flex items-center justify-center gap-2 text-gray-500 font-medium">
            <span>{candidate.creator_name}</span>
            <span>&middot;</span>
            <span>{candidate.source_type}</span>
          </div>
        </div>

        {/* Media Placeholder */}
        <div className="w-full aspect-video bg-gray-100 relative overflow-hidden group cursor-pointer border border-gray-200"
             style={candidate.thumbnail_url ? { backgroundImage: `url(${candidate.thumbnail_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}}>
           <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-transparent transition-colors">
             <span className="text-white font-medium tracking-widest uppercase group-hover:scale-105 transition-transform duration-500 bg-black/50 px-4 py-2 rounded">
               Play
             </span>
           </div>
        </div>

        {/* Editorial Explanation */}
        <div className="max-w-2xl text-center">
          <p className="text-lg md:text-xl text-gray-600 leading-relaxed font-serif italic">
            "{candidate.ai_explanation}"
          </p>
        </div>

        {/* Feedback Section */}
        <div className="mt-16 pt-16 border-t border-gray-200 w-full flex flex-col items-center gap-8">
          <h3 className="text-lg font-medium">Have you seen this before?</h3>
          <div className="flex gap-4 w-full max-w-md">
            <button className="flex-1 py-4 px-6 bg-black text-white text-sm font-bold tracking-wider uppercase hover:bg-gray-800 transition-colors">
              Never Seen It
            </button>
            <button className="flex-1 py-4 px-6 bg-white border-2 border-black text-black text-sm font-bold tracking-wider uppercase hover:bg-gray-50 transition-colors">
              I Knew This
            </button>
          </div>
        </div>

      </div>

      {/* Sliding Chat Panel */}
      <div 
        className={`fixed top-0 right-0 h-full w-full md:w-96 bg-white border-l border-gray-200 shadow-2xl transform transition-transform duration-500 ease-in-out z-50 flex flex-col ${
          isChatOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="p-6 border-b border-gray-200 flex justify-between items-center bg-gray-50">
          <div>
             <h3 className="font-bold tracking-wider uppercase text-sm">Daily Lobby</h3>
             <p className="text-xs text-gray-500">Clears at midnight</p>
          </div>
          <button 
            onClick={() => setIsChatOpen(false)}
            className="text-gray-500 hover:text-black transition-colors"
          >
            <X size={24} />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
          {comments.length === 0 ? (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm italic">
              Be the first to comment today.
            </div>
          ) : (
            comments.map((c, i) => (
              <div key={i} className="bg-gray-100 p-4 rounded-lg text-sm text-gray-800">
                <div className="font-bold text-xs text-gray-500 mb-1">Anonymous User</div>
                {c.content}
              </div>
            ))
          )}
        </div>
        
        <div className="p-4 border-t border-gray-200 bg-white">
          <form onSubmit={handleSendComment} className="flex gap-2">
            <input 
              type="text" 
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="Join the conversation..." 
              className="flex-1 bg-gray-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-black"
            />
            <button 
              type="submit"
              className="bg-black text-white p-2 rounded-full hover:bg-gray-800 transition-colors flex items-center justify-center w-10 h-10"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      </div>
      
      {/* Overlay for mobile to close chat */}
      {isChatOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-20 z-40 md:hidden"
          onClick={() => setIsChatOpen(false)}
        />
      )}

    </main>
  );
}
