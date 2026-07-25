import { useTranslation } from "react-i18next"
import { Globe } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface LanguageSwitcherProps {
  compact?: boolean
}

const LANGUAGES = [
  { code: "en", name: "English", label: "EN" },
  { code: "kn", name: "ಕನ್ನಡ", label: "ಕನ್ನಡ" },
  { code: "hi", name: "हिन्दी", label: "हिन्दी" },
]

export function LanguageSwitcher({ compact = false }: LanguageSwitcherProps) {
  const { i18n } = useTranslation()

  const handleLanguageChange = (langCode: string) => {
    i18n.changeLanguage(langCode)
    localStorage.setItem("lang", langCode)
  }

  if (compact) {
    return (
      <div className="flex items-center gap-1">
        {LANGUAGES.map((lang) => (
          <button
            key={lang.code}
            onClick={() => handleLanguageChange(lang.code)}
            className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
              i18n.language === lang.code
                ? "bg-accent-600 text-white"
                : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
            }`}
            title={lang.name}
          >
            {lang.label}
          </button>
        ))}
      </div>
    )
  }

  return (
    <Select value={i18n.language} onValueChange={handleLanguageChange}>
      <SelectTrigger className="w-40">
        <div className="flex items-center gap-2">
          <Globe className="size-4" />
          <SelectValue placeholder="Select language" />
        </div>
      </SelectTrigger>
      <SelectContent>
        {LANGUAGES.map((lang) => (
          <SelectItem key={lang.code} value={lang.code}>
            {lang.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
