export class VideoRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private canvas: HTMLCanvasElement | null = null;
  private animFrame = 0;
  private iframe: HTMLIFrameElement | null = null;
  private pendingImg: HTMLImageElement | null = null;

  get supported(): boolean {
    return typeof MediaRecorder !== 'undefined';
  }

  start(iframe: HTMLIFrameElement): boolean {
    if (!this.supported) return false;

    this.iframe = iframe;
    this.chunks = [];

    this.canvas = document.createElement('canvas');
    this.canvas.width = iframe.clientWidth;
    this.canvas.height = iframe.clientHeight;

    const stream = this.canvas.captureStream(30);

    try {
      this.mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
    } catch {
      return false;
    }

    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };

    this.mediaRecorder.start(100);
    this.drawFrame();
    return true;
  }

  private drawFrame = () => {
    if (!this.canvas || !this.iframe) return;
    const ctx = this.canvas.getContext('2d');
    if (!ctx) return;

    try {
      const doc = this.iframe.contentDocument;
      if (doc?.body) {
        const data = new XMLSerializer().serializeToString(doc);
        const blob = new Blob([data], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);
        if (this.pendingImg) this.pendingImg.onload = null;
        const img = new Image();
        this.pendingImg = img;
        img.onload = () => {
          if (!this.canvas) return;
          ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
          URL.revokeObjectURL(url);
        };
        img.src = url;
      }
    } catch {
      ctx.fillStyle = '#1e1e1e';
      ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
      ctx.fillStyle = '#666';
      ctx.fillText('Recording...', 20, 30);
    }

    this.animFrame = requestAnimationFrame(this.drawFrame);
  };

  async stop(): Promise<Blob | null> {
    cancelAnimationFrame(this.animFrame);
    if (this.pendingImg) {
      this.pendingImg.onload = null;
      this.pendingImg = null;
    }

    return new Promise((resolve) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        resolve(null);
        return;
      }

      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.chunks, { type: 'video/webm' });
        this.chunks = [];
        this.canvas = null;
        this.iframe = null;
        resolve(blob.size > 0 ? blob : null);
      };

      this.mediaRecorder.stop();
    });
  }
}
