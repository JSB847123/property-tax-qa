import { parseCsvText } from './csv'
import { koreanCategoryMap } from './categories'

export const requiredHeaders = ['분류', '제목', '출처', '내용', '전산적용', '날짜', '태그']
const markdownMetadataKeys = new Set(['분류', '제목', '출처', '날짜', '태그'])
const markdownSectionKeys = new Set(['내용', '전산적용'])
const supportedMarkdownExtensions = new Set(['.md', '.markdown'])

function detectBulkFileKind(fileName = '') {
  const normalized = fileName.toLowerCase()
  if (normalized.endsWith('.csv')) {
    return 'csv'
  }
  for (const extension of supportedMarkdownExtensions) {
    if (normalized.endsWith(extension)) {
      return 'markdown'
    }
  }
  throw new Error('대량등록은 CSV(.csv) 또는 Markdown(.md) 파일만 지원합니다.')
}

function parseTags(rawValue) {
  return rawValue ? rawValue.split(';').map((item) => item.trim()).filter(Boolean) : []
}

function buildPreviewRow(raw, index) {
  const category = koreanCategoryMap[raw['분류']] || ''
  return {
    line: index + 1,
    ...raw,
    category,
    tags: parseTags(raw['태그']),
  }
}

function collectPreviewErrors(rows) {
  return rows
    .filter((row) => !row.category || !row['제목'] || !row['출처'] || !row['내용'] || !row['날짜'])
    .map((row) => ({
      line: row.line,
      message: !row.category
        ? '분류 값이 올바르지 않습니다.'
        : '제목, 출처, 내용, 날짜는 비워둘 수 없습니다.',
    }))
}

function collectCategoryStats(rows) {
  return rows.reduce((accumulator, row) => {
    if (row.category) {
      accumulator[row.category] = (accumulator[row.category] || 0) + 1
    }
    return accumulator
  }, {})
}

function buildCsvPreview(text) {
  const rows = parseCsvText(text.replace(/^\ufeff/, ''))
  if (rows.length === 0) {
    throw new Error('CSV 내용이 비어 있습니다.')
  }

  const headers = rows[0].map((header) => header.trim())
  const missing = requiredHeaders.filter((header) => !headers.includes(header))
  if (missing.length) {
    throw new Error(`필수 헤더가 없습니다: ${missing.join(', ')}`)
  }

  const bodyRows = rows.slice(1).filter((columns) => columns.some((value) => value.trim() !== ''))
  const previewRows = bodyRows.map((columns, index) => {
    const raw = Object.fromEntries(headers.map((header, headerIndex) => [header, (columns[headerIndex] || '').trim()]))
    return buildPreviewRow(raw, index)
  })

  return {
    kind: 'csv',
    formatLabel: 'CSV',
    rows: previewRows,
    errors: collectPreviewErrors(previewRows),
    categoryStats: collectCategoryStats(previewRows),
  }
}

function stripMarkdownPrefix(value) {
  return value.replace(/^\s*[-*]\s+/, '').trim()
}

function extractMarkdownFields(block) {
  const raw = Object.fromEntries(requiredHeaders.map((header) => [header, '']))
  const bodyLines = []
  const sectionLines = { 내용: [], 전산적용: [] }
  let currentSection = null

  for (const rawLine of block.split(/\r?\n/)) {
    const line = rawLine.replace(/\s+$/, '')
    const trimmed = line.trim()

    if (!trimmed) {
      if (currentSection) {
        sectionLines[currentSection].push('')
      } else if (bodyLines.length && bodyLines[bodyLines.length - 1] !== '') {
        bodyLines.push('')
      }
      continue
    }

    const normalized = stripMarkdownPrefix(trimmed)

    if (normalized.startsWith('## ')) {
      const heading = normalized.slice(3).trim()
      if (markdownSectionKeys.has(heading)) {
        currentSection = heading
        continue
      }
    }

    if (currentSection) {
      sectionLines[currentSection].push(line)
      continue
    }

    if (normalized.startsWith('# ') && !raw['제목']) {
      raw['제목'] = normalized.slice(2).trim()
      continue
    }

    const separatorIndex = normalized.indexOf(':')
    if (separatorIndex >= 0) {
      const key = normalized.slice(0, separatorIndex).trim()
      const value = normalized.slice(separatorIndex + 1).trim()
      if (markdownSectionKeys.has(key)) {
        currentSection = key
        if (value) {
          sectionLines[key].push(value)
        }
        continue
      }
      if (markdownMetadataKeys.has(key)) {
        raw[key] = value
        continue
      }
    }

    bodyLines.push(line)
  }

  raw['내용'] = sectionLines['내용'].join('\n').trim() || bodyLines.join('\n').trim()
  raw['전산적용'] = sectionLines['전산적용'].join('\n').trim()
  return raw
}

function buildMarkdownPreview(text) {
  const normalized = text.replace(/^\ufeff/, '').trim()
  if (!normalized) {
    throw new Error('Markdown 내용이 비어 있습니다.')
  }

  const blocks = normalized.split(/(^|\r?\n)---\s*(?=\r?\n|$)/m).map((item) => item.trim()).filter(Boolean)
  if (!blocks.length) {
    throw new Error('업로드할 Markdown 문서가 없습니다.')
  }

  const previewRows = blocks.map((block, index) => buildPreviewRow(extractMarkdownFields(block), index))

  return {
    kind: 'markdown',
    formatLabel: 'Markdown',
    rows: previewRows,
    errors: collectPreviewErrors(previewRows),
    categoryStats: collectCategoryStats(previewRows),
  }
}

export function buildBulkPreview({ text, fileName }) {
  const kind = detectBulkFileKind(fileName)
  return kind === 'csv' ? buildCsvPreview(text) : buildMarkdownPreview(text)
}

