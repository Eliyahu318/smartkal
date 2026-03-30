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
        mx-5 rounded-2xl border-2 border-dashed p-8 text-center transition-colors
        ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}
        ${isDragActive ? "border-green-400 bg-green-50" : rejected ? "border-red-300 bg-red-50" : "border-gray-300 bg-gray-50 hover:border-green-300 hover:bg-green-50/50"}
      `}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3">
        {isDragActive ? (
          <>
            <FileText className="h-10 w-10 text-green-500" />
            <p className="text-sm font-medium text-green-600">שחרר כאן להעלאה</p>
          </>
        ) : (
          <>
            <Upload className="h-10 w-10 text-gray-400" />
            <p className="text-sm font-medium text-gray-600">
              גרור קובץ PDF לכאן או לחץ לבחירה
            </p>
            <p className="text-xs text-gray-400">עד 10MB · קבלות בלבד</p>
          </>
        )}
        {rejected && (
          <p className="text-xs text-red-500">
            {fileRejections[0]?.errors[0]?.code === "file-too-large"
              ? "הקובץ גדול מדי — מקסימום 10MB"
              : "יש לבחור קובץ PDF בלבד"}
          </p>
        )}
      </div>
    </div>
  );
}
