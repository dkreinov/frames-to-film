import { useState } from 'react'
import { AppBar } from '@/components/layout/AppBar'
import { PageContainer } from '@/components/layout/PageContainer'
import { Footer } from '@/components/layout/Footer'
import { Button } from '@/components/ui/button'
import { DropzoneCard } from '@/components/upload/DropzoneCard'
import { UploadedFilesList } from '@/components/upload/UploadedFilesList'
import { useUploadFlow } from './useUploadFlow'

export default function UploadScreen() {
  const [files, setFiles] = useState<File[]>([])
  const { runUpload, isRunning, error } = useUploadFlow()

  const addFiles = (incoming: File[]) =>
    setFiles((prev) => [...prev, ...incoming])

  const removeAt = (idx: number) =>
    setFiles((prev) => prev.filter((_, i) => i !== idx))

  return (
    <>
      <AppBar currentStep="upload" />
      <PageContainer
        title="Upload your photos"
        subtitle="Drop images here to get started — JPG, PNG, or WebP, up to 100 per project."
      >
        <DropzoneCard onFilesPicked={addFiles} />
        <UploadedFilesList files={files} onRemove={removeAt} />
        {error && (
          <p role="alert" className="mt-4 text-sm text-destructive">
            {error}
          </p>
        )}
      </PageContainer>

      <Footer
        right={
          <Button
            size="lg"
            disabled={files.length === 0 || isRunning}
            onClick={() =>
              runUpload(
                // auto project name from the first file's basename
                files[0]?.name.replace(/\.[^/.]+$/, '') || 'Untitled',
                files
              )
            }
          >
            {isRunning ? 'Uploading…' : 'Next: Prepare photos'}
          </Button>
        }
      />
    </>
  )
}
