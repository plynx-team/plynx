export interface ImagePreviewerProps {
  url: string;
  alt?: string;
}

export function ImagePreviewer({ url, alt = "Artifact preview" }: ImagePreviewerProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded border border-slate-800 bg-slate-950 p-6">
      <img
        src={url}
        alt={alt}
        className="max-h-[600px] max-w-full rounded object-contain shadow-md"
      />
    </div>
  );
}
