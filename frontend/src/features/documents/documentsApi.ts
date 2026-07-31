import { httpClient } from "@/lib/api/httpClient"

export interface OcrResult {
  text: string
  confidence: number
  provider: string
  note?: string
}

export interface NerEntity {
  text: string
  type: string
}

export interface NerResult {
  entities: NerEntity[]
  count: number
}

export interface UploadedDocument {
  id: string
  source_type: string
  file_format: string
  original_filename: string
  confidence_score: number
  staging_only: boolean
}

export async function ocrDocument(file: File, language?: string): Promise<OcrResult> {
  const formData = new FormData()
  formData.append("file", file)
  const response = await httpClient.post<OcrResult>("/documents/ocr", formData, {
    params: language ? { language } : undefined,
    headers: { "Content-Type": "multipart/form-data" },
  })
  return response.data
}

export async function extractEntities(text: string): Promise<NerResult> {
  const response = await httpClient.post<NerResult>("/documents/ner", { text })
  return response.data
}

export async function uploadDocument(file: File): Promise<UploadedDocument> {
  const formData = new FormData()
  formData.append("file", file)
  const response = await httpClient.post<UploadedDocument>("/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  return response.data
}

export async function promoteDocument(documentId: string): Promise<{ status: string; document_id: string }> {
  const response = await httpClient.post<{ status: string; document_id: string }>(`/documents/${documentId}/promote`)
  return response.data
}
