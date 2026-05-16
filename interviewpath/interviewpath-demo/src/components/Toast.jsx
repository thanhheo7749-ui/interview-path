function Toast({ message }) {
  if (!message) return null;

  return (
    <div className="fixed right-6 top-6 z-50 rounded-2xl border border-emerald-200 bg-white px-5 py-4 text-sm font-bold text-emerald-800 shadow-panel">
      {message}
    </div>
  );
}

export default Toast;
