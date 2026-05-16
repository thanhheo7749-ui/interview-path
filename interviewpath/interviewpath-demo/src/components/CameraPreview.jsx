import { Camera, Mic, MicOff, VideoOff } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

function CameraPreview() {
  const videoRef = useRef(null);
  const [stream, setStream] = useState(null);
  const [cameraState, setCameraState] = useState('idle');
  const [micEnabled, setMicEnabled] = useState(false);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
    return () => {
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [stream]);

  async function enableCamera() {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
      setStream(mediaStream);
      setCameraState('enabled');
    } catch {
      setCameraState('fallback');
    }
  }

  async function enableMicrophone() {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStream.getTracks().forEach((track) => track.stop());
      setMicEnabled(true);
    } catch {
      setMicEnabled(false);
    }
  }

  return (
    <section className="flex h-full flex-col rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-extrabold text-slate-950">Camera Preview</p>
          <p className="text-xs font-semibold text-slate-500">Practice mode only</p>
        </div>
        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">Private</span>
      </div>

      <div className="relative flex min-h-[280px] flex-1 items-center justify-center overflow-hidden rounded-2xl bg-slate-950">
        {cameraState === 'enabled' ? (
          <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-cover" />
        ) : (
          <div className="flex flex-col items-center text-center text-white">
            {cameraState === 'fallback' ? <VideoOff size={42} /> : <Camera size={42} />}
            <p className="mt-4 text-lg font-extrabold">{cameraState === 'fallback' ? 'Camera placeholder' : 'Camera is off'}</p>
            <p className="mt-2 max-w-[260px] text-sm leading-6 text-slate-300">
              {cameraState === 'fallback'
                ? 'Browser permission failed, so InterviewPath shows a demo placeholder.'
                : 'Enable camera when you are ready to practice.'}
            </p>
          </div>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={enableCamera}
          className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-extrabold text-white transition hover:bg-blue-700"
        >
          <Camera size={17} />
          Enable Camera
        </button>
        <button
          type="button"
          onClick={enableMicrophone}
          className="flex items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-3 text-sm font-extrabold text-white transition hover:bg-slate-800"
        >
          {micEnabled ? <Mic size={17} /> : <MicOff size={17} />}
          Enable Microphone
        </button>
      </div>
    </section>
  );
}

export default CameraPreview;
