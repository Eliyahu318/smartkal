import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText } from "lucide-react";

interface ReceiptUploadProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export function ReceiptUpload({ onFileSelected, disabled }: ReceiptUploadProps) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) {
        onFileSelected(accepted[0]!);
      }
    },
    [onFileSelected],
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } =
    useDropzone({
      onDrop,
      accept: { "application/pdf": [".pdf"] },
      maxSize: 10 * 1024 * 1024, // 10MB
      maxFiles: 1,
      disabled,
    });

  const rejected = fileRejections.length > 0;

  return (
    <div
      {...getRootProps()}
      data-testid="receipt-dropzone"
      className={`
        mx-5 rounded-ios-lg border-2 border-dashed p-8 text-center transition-all
        ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}
        ${
          isDragActive
            ? "border-brand bg-brand/10 shadow-ios-lg ring-2 ring-brand/30"
            : rejected
              ? "border-danger/50 bg-danger/10"
              : "border-separator-opaque bg-surface hover:border-brand/40 hover:bg-brand/5"
        }
      `}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3">
        {isDragActive ? (
          <>
            <FileText className="h-10 w-10 text-brand" />
            <p className="text-callout font-medium text-brand">
              שחרר כאן להעלאה
            </p>
          </>
        ) : (
          <>
            <Upload className="h-10 w-10 text-label-tertiary/70" />
            <p className="text-callout font-medium text-label-secondary">
              גרור קובץ PDF לכאן או לחץ לבחירה
            </p>
            <p className="text-caption1 text-label-tertiary/70">
              עד 10MB · קבלות בלבד
            </p>
          </>
        )}
        {rejected && (
          <p className="text-caption1 text-danger">
            {fileRejections[0]?.errors[0]?.code === "file-too-large"
              ? "הקובץ גדול מדי — מקסימום 10MB"
              : "יש לבחור קובץ PDF בלבד"}
          </p>
        )}
      </div>
    </div>
  );
}
