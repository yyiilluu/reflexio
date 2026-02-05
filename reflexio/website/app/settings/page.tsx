"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Settings,
  Database,
  Brain,
  MessageSquare,
  CheckCircle,
  Sliders,
  Save,
  Plus,
  Trash2,
  AlertCircle,
  Workflow,
  ChevronDown,
  ChevronUp,
  Key,
} from "lucide-react"
import { getConfig, setConfig as setConfigAPI } from "@/lib/api"
import WorkflowVisualization from "@/components/workflow/WorkflowVisualization"

// Types matching the config schema
type StorageType = "local" | "supabase"

interface StorageConfigLocal {
  type: "local"
  dir_path: string
}

interface StorageConfigSupabase {
  type: "supabase"
  url: string
  key: string
  db_url: string
}

type StorageConfig = StorageConfigLocal | StorageConfigSupabase

// Frontend config types (with id for UI management)
interface ProfileExtractorConfig {
  id: string
  extractor_name: string
  profile_content_definition_prompt: string
  context_prompt?: string
  metadata_definition_prompt?: string
  should_extract_profile_prompt_override?: string
  request_sources_enabled?: string[]
  manual_trigger?: boolean
  extraction_window_size_override?: number
  extraction_window_stride_override?: number
}

interface FeedbackAggregatorConfig {
  min_feedback_threshold: number
  refresh_count: number
}

interface AgentFeedbackConfig {
  id: string
  feedback_name: string
  feedback_definition_prompt: string
  metadata_definition_prompt?: string
  request_sources_enabled?: string[]
  feedback_aggregator_config?: FeedbackAggregatorConfig
  extraction_window_size_override?: number
  extraction_window_stride_override?: number
}

interface ToolUseConfig {
  tool_name: string
  tool_description: string
}

interface AgentSuccessConfig {
  id: string
  evaluation_name: string
  success_definition_prompt: string
  tool_can_use?: ToolUseConfig[]
  action_space?: string[]
  metadata_definition_prompt?: string
  sampling_rate?: number
  extraction_window_size_override?: number
  extraction_window_stride_override?: number
}

// API Key configuration types
interface AzureOpenAIConfig {
  api_key: string
  endpoint: string
  api_version: string
  deployment_name?: string
}

interface OpenAIConfig {
  api_key?: string
  azure_config?: AzureOpenAIConfig
}

interface AnthropicConfig {
  api_key: string
}

interface OpenRouterConfig {
  api_key: string
}

interface APIKeyConfig {
  openai?: OpenAIConfig
  anthropic?: AnthropicConfig
  openrouter?: OpenRouterConfig
}

// LLM model configuration overrides
interface LLMConfig {
  should_run_model_name?: string
  generation_model_name?: string
  embedding_model_name?: string
}

interface Config {
  storage_config: StorageConfig
  agent_context_prompt?: string
  profile_extractor_configs: ProfileExtractorConfig[]
  agent_feedback_configs: AgentFeedbackConfig[]
  agent_success_configs: AgentSuccessConfig[]
  extraction_window_size?: number
  extraction_window_stride?: number
  api_key_config?: APIKeyConfig
  llm_config?: LLMConfig
}

// Backend config types (without id, matches Python schema)
interface BackendProfileExtractorConfig {
  extractor_name: string
  profile_content_definition_prompt: string
  context_prompt?: string
  metadata_definition_prompt?: string
  should_extract_profile_prompt_override?: string
  request_sources_enabled?: string[]
  manual_trigger?: boolean
  extraction_window_size_override?: number
  extraction_window_stride_override?: number
}

interface BackendAgentFeedbackConfig {
  feedback_name: string
  feedback_definition_prompt: string
  metadata_definition_prompt?: string
  request_sources_enabled?: string[]
  feedback_aggregator_config?: FeedbackAggregatorConfig
  extraction_window_size_override?: number
  extraction_window_stride_override?: number
}

interface BackendAgentSuccessConfig {
  evaluation_name: string
  success_definition_prompt: string
  tool_can_use?: ToolUseConfig[]
  action_space?: string[]
  metadata_definition_prompt?: string
  sampling_rate?: number
  extraction_window_size_override?: number
  extraction_window_stride_override?: number
}

interface BackendConfig {
  storage_config: StorageConfig
  agent_context_prompt?: string
  profile_extractor_configs?: BackendProfileExtractorConfig[]
  agent_feedback_configs?: BackendAgentFeedbackConfig[]
  agent_success_configs?: BackendAgentSuccessConfig[]
  extraction_window_size?: number
  extraction_window_stride?: number
  api_key_config?: APIKeyConfig
  llm_config?: LLMConfig
}

// Helper function to generate unique IDs
const generateId = () => Math.random().toString(36).substring(2, 9)

// Helper function to infer storage type and add type field
const inferStorageConfig = (storageConfig: any): StorageConfig => {
  // Handle null or undefined storage config - return default local storage
  if (!storageConfig) {
    return {
      type: "local",
      dir_path: "",
    }
  }
  if ("dir_path" in storageConfig) {
    return {
      type: "local",
      dir_path: storageConfig.dir_path,
    }
  } else if ("url" in storageConfig && "key" in storageConfig) {
    return {
      type: "supabase",
      url: storageConfig.url,
      key: storageConfig.key,
      db_url: storageConfig.db_url,
    }
  }
  // Default to local storage
  return {
    type: "local",
    dir_path: "",
  }
}

// Helper function to deep compare configs for unsaved changes detection
const configsAreEqual = (config1: Config, config2: Config): boolean => {
  // Compare storage configs
  if (JSON.stringify(config1.storage_config) !== JSON.stringify(config2.storage_config)) {
    return false
  }

  // Compare agent context prompt
  if ((config1.agent_context_prompt || "") !== (config2.agent_context_prompt || "")) {
    return false
  }

  // Compare extraction window settings
  if (config1.extraction_window_size !== config2.extraction_window_size ||
      config1.extraction_window_stride !== config2.extraction_window_stride) {
    return false
  }

  // Compare API key configs
  if (JSON.stringify(config1.api_key_config || {}) !== JSON.stringify(config2.api_key_config || {})) {
    return false
  }

  // Compare LLM configs
  if (JSON.stringify(config1.llm_config || {}) !== JSON.stringify(config2.llm_config || {})) {
    return false
  }

  // Compare profile extractors (ignoring ids)
  const extractors1 = config1.profile_extractor_configs.map(({ id, ...rest }) => rest)
  const extractors2 = config2.profile_extractor_configs.map(({ id, ...rest }) => rest)
  if (JSON.stringify(extractors1) !== JSON.stringify(extractors2)) {
    return false
  }

  // Compare agent feedback configs (ignoring ids)
  const feedback1 = config1.agent_feedback_configs.map(({ id, ...rest }) => rest)
  const feedback2 = config2.agent_feedback_configs.map(({ id, ...rest }) => rest)
  if (JSON.stringify(feedback1) !== JSON.stringify(feedback2)) {
    return false
  }

  // Compare agent success configs (ignoring ids)
  const success1 = config1.agent_success_configs.map(({ id, ...rest }) => rest)
  const success2 = config2.agent_success_configs.map(({ id, ...rest }) => rest)
  if (JSON.stringify(success1) !== JSON.stringify(success2)) {
    return false
  }

  return true
}

// Helper functions to convert between backend and frontend configs
const backendToFrontendConfig = (backendConfig: BackendConfig): Config => {
  return {
    storage_config: inferStorageConfig(backendConfig.storage_config),
    agent_context_prompt: backendConfig.agent_context_prompt,
    profile_extractor_configs: (backendConfig.profile_extractor_configs || []).map(config => ({
      id: generateId(),
      ...config,
    })),
    agent_feedback_configs: (backendConfig.agent_feedback_configs || []).map(config => ({
      id: generateId(),
      ...config,
    })),
    agent_success_configs: (backendConfig.agent_success_configs || []).map(config => ({
      id: generateId(),
      ...config,
    })),
    extraction_window_size: backendConfig.extraction_window_size,
    extraction_window_stride: backendConfig.extraction_window_stride,
    api_key_config: backendConfig.api_key_config,
    llm_config: backendConfig.llm_config,
  }
}

const frontendToBackendConfig = (config: Config): BackendConfig => {
  // Remove the 'type' field from storage_config for backend
  const { type, ...storageConfigWithoutType } = config.storage_config

  return {
    storage_config: storageConfigWithoutType as any,
    agent_context_prompt: config.agent_context_prompt,
    profile_extractor_configs: config.profile_extractor_configs.map(({ id, ...rest }) => rest),
    agent_feedback_configs: config.agent_feedback_configs.map(({ id, ...rest }) => rest),
    agent_success_configs: config.agent_success_configs.map(({ id, ...rest }) => rest),
    extraction_window_size: config.extraction_window_size,
    extraction_window_stride: config.extraction_window_stride,
    api_key_config: config.api_key_config,
    llm_config: config.llm_config,
  }
}

// Default configuration
const getDefaultConfig = (): Config => ({
  storage_config: {
    type: "local",
    dir_path: "./data",
  },
  agent_context_prompt: "",
  profile_extractor_configs: [],
  agent_feedback_configs: [],
  agent_success_configs: [],
  extraction_window_size: 10,
  extraction_window_stride: 5,
})

export default function SettingsPage() {
  const [config, setConfig] = useState<Config>(getDefaultConfig())
  const [originalConfig, setOriginalConfig] = useState<Config>(getDefaultConfig())
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle")
  const [loading, setLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string>("")
  const [activeTab, setActiveTab] = useState<"general" | "extractors" | "workflow">("general")
  const [advancedSettingsExpanded, setAdvancedSettingsExpanded] = useState(false)
  const [openaiMode, setOpenaiMode] = useState<"direct" | "azure">("direct")

  // Compute whether there are unsaved changes
  const hasUnsavedChanges = !loading && !configsAreEqual(config, originalConfig)

  // Fetch config from backend on mount
  useEffect(() => {
    const fetchConfigData = async () => {
      try {
        const backendConfig = await getConfig()
        const frontendConfig = backendToFrontendConfig(backendConfig as BackendConfig)
        setConfig(frontendConfig)
        setOriginalConfig(frontendConfig) // Store original config
        // Set OpenAI mode based on loaded config
        if (frontendConfig.api_key_config?.openai?.azure_config) {
          setOpenaiMode("azure")
        }
      } catch (error) {
        console.error("Error fetching config:", error)
        setErrorMessage(error instanceof Error ? error.message : "Failed to load configuration")
        // Keep default config on error
      } finally {
        setLoading(false)
      }
    }

    fetchConfigData()
  }, [])

  // Helper functions for API key config updates
  const updateOpenAIConfig = (updates: Partial<OpenAIConfig>) => {
    setConfig({
      ...config,
      api_key_config: {
        ...config.api_key_config,
        openai: {
          ...config.api_key_config?.openai,
          ...updates,
        },
      },
    })
  }

  const updateAzureOpenAIConfig = (updates: Partial<AzureOpenAIConfig>) => {
    setConfig({
      ...config,
      api_key_config: {
        ...config.api_key_config,
        openai: {
          ...config.api_key_config?.openai,
          azure_config: {
            api_key: config.api_key_config?.openai?.azure_config?.api_key || "",
            endpoint: config.api_key_config?.openai?.azure_config?.endpoint || "",
            api_version: config.api_key_config?.openai?.azure_config?.api_version || "2024-02-15-preview",
            ...config.api_key_config?.openai?.azure_config,
            ...updates,
          },
        },
      },
    })
  }

  const updateAnthropicConfig = (updates: Partial<AnthropicConfig>) => {
    setConfig({
      ...config,
      api_key_config: {
        ...config.api_key_config,
        anthropic: {
          api_key: config.api_key_config?.anthropic?.api_key || "",
          ...config.api_key_config?.anthropic,
          ...updates,
        },
      },
    })
  }

  const updateOpenRouterConfig = (updates: Partial<OpenRouterConfig>) => {
    setConfig({
      ...config,
      api_key_config: {
        ...config.api_key_config,
        openrouter: {
          api_key: config.api_key_config?.openrouter?.api_key || "",
          ...config.api_key_config?.openrouter,
          ...updates,
        },
      },
    })
  }

  const updateLLMConfig = (updates: Partial<LLMConfig>) => {
    setConfig({
      ...config,
      llm_config: {
        ...config.llm_config,
        ...updates,
      },
    })
  }

  const handleOpenAIModeChange = (mode: "direct" | "azure") => {
    setOpenaiMode(mode)
    if (mode === "direct") {
      // Clear Azure config when switching to direct mode
      updateOpenAIConfig({ azure_config: undefined })
    } else {
      // Clear direct API key when switching to Azure mode
      updateOpenAIConfig({
        api_key: undefined,
        azure_config: {
          api_key: "",
          endpoint: "",
          api_version: "2024-02-15-preview",
        },
      })
    }
  }

  const handleSave = async () => {
    setSaveStatus("saving")
    setErrorMessage("")

    // Validate required fields for Supabase storage
    if (config.storage_config.type === "supabase") {
      const supabaseConfig = config.storage_config as StorageConfigSupabase
      if (!supabaseConfig.url || !supabaseConfig.key || !supabaseConfig.db_url) {
        const missingFields = []
        if (!supabaseConfig.url) missingFields.push("Supabase URL")
        if (!supabaseConfig.key) missingFields.push("Supabase Key")
        if (!supabaseConfig.db_url) missingFields.push("Database URL")
        setErrorMessage(`Required fields missing: ${missingFields.join(", ")}`)
        setSaveStatus("error")
        setTimeout(() => setSaveStatus("idle"), 3000)
        return
      }
    }

    try {
      const backendConfig = frontendToBackendConfig(config)
      const result = await setConfigAPI(backendConfig as any)

      if (!result.success) {
        // If success is false, show the error message from the API
        const errorMsg = result.msg || "Failed to save configuration"
        setErrorMessage(errorMsg)
        setSaveStatus("error")
        setTimeout(() => setSaveStatus("idle"), 3000)
        return
      }

      // Update original config to the newly saved config
      setOriginalConfig(config)
      setSaveStatus("success")
      setTimeout(() => setSaveStatus("idle"), 3000)
    } catch (error) {
      console.error("Error saving config:", error)
      setErrorMessage(error instanceof Error ? error.message : "Failed to save configuration")
      setSaveStatus("error")
      setTimeout(() => setSaveStatus("idle"), 3000)
    }
  }

  const updateStorageConfig = (updates: Partial<StorageConfig>) => {
    setConfig({
      ...config,
      storage_config: { ...config.storage_config, ...updates } as StorageConfig,
    })
  }

  const changeStorageType = (type: StorageType) => {
    let newStorageConfig: StorageConfig

    // Check if the original config has this storage type and use it
    if (originalConfig.storage_config.type === type) {
      newStorageConfig = originalConfig.storage_config
    } else {
      // Use sensible defaults for new storage types
      switch (type) {
        case "local":
          newStorageConfig = { type: "local", dir_path: "./data" }
          break
        case "supabase":
          newStorageConfig = { type: "supabase", url: "", key: "", db_url: "" }
          break
      }
    }

    setConfig({ ...config, storage_config: newStorageConfig })
  }

  const addProfileExtractor = () => {
    setConfig({
      ...config,
      profile_extractor_configs: [
        ...config.profile_extractor_configs,
        {
          id: generateId(),
          extractor_name: "",
          profile_content_definition_prompt: "",
          context_prompt: "",
          metadata_definition_prompt: "",
          manual_trigger: false,
        },
      ],
    })
  }

  const updateProfileExtractor = (id: string, updates: Partial<ProfileExtractorConfig>) => {
    setConfig({
      ...config,
      profile_extractor_configs: config.profile_extractor_configs.map(pec =>
        pec.id === id ? { ...pec, ...updates } : pec
      ),
    })
  }

  const removeProfileExtractor = (id: string) => {
    setConfig({
      ...config,
      profile_extractor_configs: config.profile_extractor_configs.filter(pec => pec.id !== id),
    })
  }

  const addRequestSourceToExtractor = (extractorId: string, source: string) => {
    const extractor = config.profile_extractor_configs.find(pec => pec.id === extractorId)
    if (extractor) {
      updateProfileExtractor(extractorId, {
        request_sources_enabled: [...(extractor.request_sources_enabled || []), source],
      })
    }
  }

  const removeRequestSourceFromExtractor = (extractorId: string, sourceIndex: number) => {
    const extractor = config.profile_extractor_configs.find(pec => pec.id === extractorId)
    if (extractor && extractor.request_sources_enabled) {
      updateProfileExtractor(extractorId, {
        request_sources_enabled: extractor.request_sources_enabled.filter((_, idx) => idx !== sourceIndex),
      })
    }
  }

  const addRequestSourceToFeedback = (feedbackId: string, source: string) => {
    const feedback = config.agent_feedback_configs.find(afc => afc.id === feedbackId)
    if (feedback) {
      updateAgentFeedback(feedbackId, {
        request_sources_enabled: [...(feedback.request_sources_enabled || []), source],
      })
    }
  }

  const removeRequestSourceFromFeedback = (feedbackId: string, sourceIndex: number) => {
    const feedback = config.agent_feedback_configs.find(afc => afc.id === feedbackId)
    if (feedback && feedback.request_sources_enabled) {
      updateAgentFeedback(feedbackId, {
        request_sources_enabled: feedback.request_sources_enabled.filter((_, idx) => idx !== sourceIndex),
      })
    }
  }

  const addAgentFeedback = () => {
    setConfig({
      ...config,
      agent_feedback_configs: [
        ...config.agent_feedback_configs,
        {
          id: generateId(),
          feedback_name: "",
          feedback_definition_prompt: "",
          feedback_aggregator_config: { min_feedback_threshold: 2, refresh_count: 2 },
        },
      ],
    })
  }

  const updateAgentFeedback = (id: string, updates: Partial<AgentFeedbackConfig>) => {
    setConfig({
      ...config,
      agent_feedback_configs: config.agent_feedback_configs.map(afc =>
        afc.id === id ? { ...afc, ...updates } : afc
      ),
    })
  }

  const removeAgentFeedback = (id: string) => {
    setConfig({
      ...config,
      agent_feedback_configs: config.agent_feedback_configs.filter(afc => afc.id !== id),
    })
  }

  const addAgentSuccess = () => {
    setConfig({
      ...config,
      agent_success_configs: [
        ...config.agent_success_configs,
        {
          id: generateId(),
          evaluation_name: "",
          success_definition_prompt: "",
          tool_can_use: [],
          action_space: [],
        },
      ],
    })
  }

  const updateAgentSuccess = (id: string, updates: Partial<AgentSuccessConfig>) => {
    setConfig({
      ...config,
      agent_success_configs: config.agent_success_configs.map(asc =>
        asc.id === id ? { ...asc, ...updates } : asc
      ),
    })
  }

  const removeAgentSuccess = (id: string) => {
    setConfig({
      ...config,
      agent_success_configs: config.agent_success_configs.filter(asc => asc.id !== id),
    })
  }

  const addToolToSuccess = (successId: string) => {
    const successConfig = config.agent_success_configs.find(asc => asc.id === successId)
    if (successConfig) {
      updateAgentSuccess(successId, {
        tool_can_use: [...(successConfig.tool_can_use || []), { tool_name: "", tool_description: "" }],
      })
    }
  }

  const updateToolInSuccess = (successId: string, toolIndex: number, updates: Partial<ToolUseConfig>) => {
    const successConfig = config.agent_success_configs.find(asc => asc.id === successId)
    if (successConfig && successConfig.tool_can_use) {
      const updatedTools = successConfig.tool_can_use.map((tool, idx) =>
        idx === toolIndex ? { ...tool, ...updates } : tool
      )
      updateAgentSuccess(successId, { tool_can_use: updatedTools })
    }
  }

  const removeToolFromSuccess = (successId: string, toolIndex: number) => {
    const successConfig = config.agent_success_configs.find(asc => asc.id === successId)
    if (successConfig && successConfig.tool_can_use) {
      updateAgentSuccess(successId, {
        tool_can_use: successConfig.tool_can_use.filter((_, idx) => idx !== toolIndex),
      })
    }
  }

  const addActionToSuccess = (successId: string, action: string) => {
    const successConfig = config.agent_success_configs.find(asc => asc.id === successId)
    if (successConfig) {
      updateAgentSuccess(successId, {
        action_space: [...(successConfig.action_space || []), action],
      })
    }
  }

  const removeActionFromSuccess = (successId: string, actionIndex: number) => {
    const successConfig = config.agent_success_configs.find(asc => asc.id === successId)
    if (successConfig && successConfig.action_space) {
      updateAgentSuccess(successId, {
        action_space: successConfig.action_space.filter((_, idx) => idx !== actionIndex),
      })
    }
  }

  // Show loading spinner while fetching config
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-10 w-10 border-2 border-transparent border-t-indigo-500 border-r-indigo-500"></div>
          <p className="text-slate-500">Loading configuration...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-50">
      <div className="bg-white/80 backdrop-blur-sm border-b border-slate-200/50">
        <div className="p-8">
          <div className="max-w-[1800px] mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                  <Settings className="h-5 w-5 text-white" />
                </div>
                <h1 className="text-3xl font-bold tracking-tight text-slate-800">Settings</h1>
              </div>
              <p className="text-slate-500 mt-1 ml-13">
                Configure storage, extractors, and evaluation criteria
              </p>
            </div>
            <div className="flex items-center gap-3">
              {hasUnsavedChanges && (
                <span className="text-xs text-amber-600 font-medium flex items-center gap-1.5 bg-amber-50 px-3 py-1.5 rounded-lg border border-amber-200">
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                  Unsaved changes
                </span>
              )}
              <Button onClick={handleSave} disabled={saveStatus === "saving"} size="lg" className={`shadow-lg border-0 ${hasUnsavedChanges ? "shadow-amber-500/25 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600" : "shadow-indigo-500/25 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"}`}>
                <Save className="h-4 w-4 mr-2" />
                {saveStatus === "saving" ? "Saving..." : "Save Configuration"}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="p-8">
        <div className="max-w-[1800px] mx-auto">

          {/* Unsaved Changes Warning Banner */}
          {hasUnsavedChanges && saveStatus !== "saving" && (
            <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-3 shadow-sm">
              <div className="h-8 w-8 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <p className="text-sm text-amber-800 font-semibold">You have unsaved changes</p>
                <p className="text-xs text-amber-600 mt-0.5">Your configuration has been modified. Don't forget to save before leaving.</p>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {errorMessage && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3 shadow-sm">
              <AlertCircle className="h-5 w-5 text-red-500" />
              <p className="text-sm text-red-600 font-medium">{errorMessage}</p>
            </div>
          )}

          {/* Save Status Banner */}
          {saveStatus === "success" && (
            <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-3 shadow-sm">
              <CheckCircle className="h-5 w-5 text-emerald-500" />
              <p className="text-sm text-emerald-700 font-medium">Configuration saved successfully!</p>
            </div>
          )}

          {saveStatus === "error" && !errorMessage && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3 shadow-sm">
              <AlertCircle className="h-5 w-5 text-red-500" />
              <p className="text-sm text-red-600 font-medium">Failed to save configuration. Please try again.</p>
            </div>
          )}

          {/* Tab Navigation */}
          <div className="mb-6">
            <div className="border-b border-slate-200">
              <div className="flex gap-1">
                <button
                  onClick={() => setActiveTab("general")}
                  className={`px-6 py-3 text-sm font-medium transition-colors relative ${
                    activeTab === "general"
                      ? "text-indigo-600"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  General Settings
                  {activeTab === "general" && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500 to-purple-500" />
                  )}
                </button>
                <button
                  onClick={() => setActiveTab("extractors")}
                  className={`px-6 py-3 text-sm font-medium transition-colors relative ${
                    activeTab === "extractors"
                      ? "text-indigo-600"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  Extractor Settings
                  {activeTab === "extractors" && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500 to-purple-500" />
                  )}
                </button>
                <button
                  onClick={() => setActiveTab("workflow")}
                  className={`px-6 py-3 text-sm font-medium transition-colors relative flex items-center gap-2 ${
                    activeTab === "workflow"
                      ? "text-indigo-600"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  <Workflow className="h-4 w-4" />
                  Workflow Visualization
                  {activeTab === "workflow" && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500 to-purple-500" />
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Tab Content */}
          {activeTab === "general" && (
            <div className="space-y-6">{/* General Settings Content */}

              {/* Storage Configuration */}
              <Card className="border-slate-200 bg-white overflow-hidden hover:shadow-lg transition-all duration-300">
              <CardHeader className="pb-4">
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center shadow-lg">
                    <Database className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-lg font-semibold text-slate-800">Storage Configuration</CardTitle>
                    <CardDescription className="text-xs mt-1 text-slate-500">Configure data storage backend</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-2 block text-slate-700">Storage Type</label>
                  <select
                    value={config.storage_config.type}
                    onChange={(e) => changeStorageType(e.target.value as StorageType)}
                    className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300"
                  >
                    <option value="local">Local Storage</option>
                    <option value="supabase">Supabase</option>
                  </select>
                </div>

                {config.storage_config.type === "local" && (
                  <div>
                    <label className="text-sm font-medium mb-2 block">Directory Path</label>
                    <Input
                      value={config.storage_config.dir_path}
                      onChange={(e) => updateStorageConfig({ dir_path: e.target.value })}
                      placeholder="/path/to/storage"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Local directory path for storing data
                    </p>
                  </div>
                )}

                {config.storage_config.type === "supabase" && (
                  <div className="space-y-3">
                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        Supabase URL <span className="text-red-500">*</span>
                      </label>
                      <Input
                        value={config.storage_config.url}
                        onChange={(e) => updateStorageConfig({ url: e.target.value })}
                        placeholder="https://xxx.supabase.co"
                        required
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        Supabase Key <span className="text-red-500">*</span>
                      </label>
                      <Input
                        type="password"
                        value={config.storage_config.key}
                        onChange={(e) => updateStorageConfig({ key: e.target.value })}
                        placeholder="Supabase API Key"
                        required
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        Database URL <span className="text-red-500">*</span>
                      </label>
                      <Input
                        value={config.storage_config.db_url}
                        onChange={(e) => updateStorageConfig({ db_url: e.target.value })}
                        placeholder="postgresql://..."
                        required
                      />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Agent Context */}
            <Card className="border-slate-200 bg-white overflow-hidden hover:shadow-lg transition-all duration-300">
              <CardHeader className="pb-4">
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-lg">
                    <Brain className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-lg font-semibold text-slate-800">Agent Context</CardTitle>
                    <CardDescription className="text-xs mt-1 text-slate-500">Define agent working environment</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div>
                  <label className="text-sm font-medium mb-2 block text-slate-700">Agent Context Prompt</label>
                  <textarea
                    value={config.agent_context_prompt || ""}
                    onChange={(e) => setConfig({ ...config, agent_context_prompt: e.target.value })}
                    className="flex min-h-[200px] w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 resize-y"
                    placeholder="Define agent working environment, tools available, and action space..."
                    rows={8}
                  />
                  <p className="text-xs text-slate-500 mt-2">
                    Define the agent's working environment, available tools, and action space
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Extraction Parameters */}
            <Card className="border-slate-200 bg-white overflow-hidden hover:shadow-lg transition-all duration-300">
              <CardHeader className="pb-4">
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-lg">
                    <Sliders className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-lg font-semibold text-slate-800">Extraction Parameters</CardTitle>
                    <CardDescription className="text-xs mt-1 text-slate-500">Configure extraction window settings</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="text-sm font-medium mb-2 block">Window Size</label>
                    <Input
                      type="number"
                      min="1"
                      value={config.extraction_window_size ?? ""}
                      onChange={(e) => setConfig({
                        ...config,
                        extraction_window_size: e.target.value ? parseInt(e.target.value) : undefined
                      })}
                      placeholder="10"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Interactions per window
                    </p>
                  </div>

                  <div>
                    <label className="text-sm font-medium mb-2 block">Window Stride</label>
                    <Input
                      type="number"
                      min="1"
                      value={config.extraction_window_stride ?? ""}
                      onChange={(e) => setConfig({
                        ...config,
                        extraction_window_stride: e.target.value ? parseInt(e.target.value) : undefined
                      })}
                      placeholder="5"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Skip between windows
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Advanced Settings - Collapsible */}
            <Card className="border-slate-200 bg-white overflow-hidden hover:shadow-lg transition-all duration-300">
              <CardHeader
                className="pb-4 cursor-pointer select-none"
                onClick={() => setAdvancedSettingsExpanded(!advancedSettingsExpanded)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-slate-600 to-slate-700 flex items-center justify-center shadow-lg">
                      <Key className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <CardTitle className="text-lg font-semibold text-slate-800">Advanced Settings</CardTitle>
                      <CardDescription className="text-xs mt-1 text-slate-500">API keys and provider configuration</CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {(config.api_key_config?.openai?.api_key || config.api_key_config?.openai?.azure_config?.api_key || config.api_key_config?.anthropic?.api_key || config.api_key_config?.openrouter?.api_key || config.llm_config?.should_run_model_name || config.llm_config?.generation_model_name || config.llm_config?.embedding_model_name) && (
                      <Badge className="text-xs bg-emerald-100 text-emerald-700 hover:bg-emerald-100">
                        Configured
                      </Badge>
                    )}
                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                      {advancedSettingsExpanded ? (
                        <ChevronUp className="h-5 w-5 text-slate-500" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-slate-500" />
                      )}
                    </Button>
                  </div>
                </div>
              </CardHeader>

              {advancedSettingsExpanded && (
                <CardContent className="space-y-6 pt-0">
                  {/* OpenAI Configuration */}
                  <div className="p-5 border rounded-lg space-y-4 bg-muted/30">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
                          <span className="text-white text-xs font-bold">AI</span>
                        </div>
                        <span className="text-sm font-semibold text-slate-800">OpenAI Configuration</span>
                      </div>
                    </div>

                    {/* OpenAI Mode Toggle */}
                    <div>
                      <label className="text-sm font-medium mb-2 block text-slate-700">Provider Mode</label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => handleOpenAIModeChange("direct")}
                          className={`flex-1 h-10 px-4 rounded-lg text-sm font-medium transition-all border ${
                            openaiMode === "direct"
                              ? "bg-indigo-50 text-indigo-700 border-indigo-200 shadow-sm"
                              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                          }`}
                        >
                          Direct OpenAI
                        </button>
                        <button
                          type="button"
                          onClick={() => handleOpenAIModeChange("azure")}
                          className={`flex-1 h-10 px-4 rounded-lg text-sm font-medium transition-all border ${
                            openaiMode === "azure"
                              ? "bg-indigo-50 text-indigo-700 border-indigo-200 shadow-sm"
                              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                          }`}
                        >
                          Azure OpenAI
                        </button>
                      </div>
                    </div>

                    {openaiMode === "direct" ? (
                      <div>
                        <label className="text-sm font-medium mb-2 block text-slate-700">OpenAI API Key</label>
                        <Input
                          type="password"
                          value={config.api_key_config?.openai?.api_key || ""}
                          onChange={(e) => updateOpenAIConfig({ api_key: e.target.value })}
                          placeholder="sk-..."
                          className="h-10"
                        />
                        <p className="text-xs text-slate-500 mt-2">
                          Your OpenAI API key for direct API access
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="grid gap-4 sm:grid-cols-2">
                          <div>
                            <label className="text-sm font-medium mb-2 block text-slate-700">Azure API Key</label>
                            <Input
                              type="password"
                              value={config.api_key_config?.openai?.azure_config?.api_key || ""}
                              onChange={(e) => updateAzureOpenAIConfig({ api_key: e.target.value })}
                              placeholder="Azure OpenAI API Key"
                              className="h-10"
                            />
                          </div>
                          <div>
                            <label className="text-sm font-medium mb-2 block text-slate-700">Endpoint</label>
                            <Input
                              type="text"
                              value={config.api_key_config?.openai?.azure_config?.endpoint || ""}
                              onChange={(e) => updateAzureOpenAIConfig({ endpoint: e.target.value })}
                              placeholder="https://your-resource.openai.azure.com/"
                              className="h-10"
                            />
                          </div>
                        </div>
                        <div className="grid gap-4 sm:grid-cols-2">
                          <div>
                            <label className="text-sm font-medium mb-2 block text-slate-700">API Version</label>
                            <Input
                              type="text"
                              value={config.api_key_config?.openai?.azure_config?.api_version || "2024-02-15-preview"}
                              onChange={(e) => updateAzureOpenAIConfig({ api_version: e.target.value })}
                              placeholder="2024-02-15-preview"
                              className="h-10"
                            />
                          </div>
                          <div>
                            <label className="text-sm font-medium mb-2 block text-slate-700">Deployment Name (Optional)</label>
                            <Input
                              type="text"
                              value={config.api_key_config?.openai?.azure_config?.deployment_name || ""}
                              onChange={(e) => updateAzureOpenAIConfig({ deployment_name: e.target.value || undefined })}
                              placeholder="gpt-4"
                              className="h-10"
                            />
                          </div>
                        </div>
                        <p className="text-xs text-slate-500">
                          Configure Azure OpenAI Service credentials for enterprise deployments
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Anthropic Configuration */}
                  <div className="p-5 border rounded-lg space-y-4 bg-muted/30">
                    <div className="flex items-center gap-2">
                      <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center">
                        <span className="text-white text-xs font-bold">A</span>
                      </div>
                      <span className="text-sm font-semibold text-slate-800">Anthropic Configuration</span>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block text-slate-700">Anthropic API Key</label>
                      <Input
                        type="password"
                        value={config.api_key_config?.anthropic?.api_key || ""}
                        onChange={(e) => updateAnthropicConfig({ api_key: e.target.value })}
                        placeholder="sk-ant-..."
                        className="h-10"
                      />
                      <p className="text-xs text-slate-500 mt-2">
                        Your Anthropic API key for Claude models
                      </p>
                    </div>
                  </div>

                  {/* OpenRouter Configuration */}
                  <div className="p-5 border rounded-lg space-y-4 bg-muted/30">
                    <div className="flex items-center gap-2">
                      <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
                        <span className="text-white text-xs font-bold">OR</span>
                      </div>
                      <span className="text-sm font-semibold text-slate-800">OpenRouter Configuration</span>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block text-slate-700">OpenRouter API Key</label>
                      <Input
                        type="password"
                        value={config.api_key_config?.openrouter?.api_key || ""}
                        onChange={(e) => updateOpenRouterConfig({ api_key: e.target.value })}
                        placeholder="sk-or-..."
                        className="h-10"
                      />
                      <p className="text-xs text-slate-500 mt-2">
                        Your OpenRouter API key for accessing multiple providers
                      </p>
                    </div>
                  </div>

                  {/* LLM Model Configuration */}
                  <div className="p-5 border rounded-lg space-y-4 bg-muted/30">
                    <div className="flex items-center gap-2">
                      <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
                        <span className="text-white text-xs font-bold">M</span>
                      </div>
                      <span className="text-sm font-semibold text-slate-800">LLM Model Configuration</span>
                    </div>
                    <p className="text-xs text-slate-500">
                      Override default model names. Leave empty to use system defaults from site configuration.
                    </p>

                    <div className="grid gap-4 sm:grid-cols-3">
                      <div>
                        <label className="text-sm font-medium mb-2 block text-slate-700">Should Run Model</label>
                        <Input
                          type="text"
                          value={config.llm_config?.should_run_model_name || ""}
                          onChange={(e) => updateLLMConfig({ should_run_model_name: e.target.value || undefined })}
                          placeholder="e.g., gpt-5-nano"
                          className="h-10"
                        />
                        <p className="text-xs text-slate-500 mt-1">
                          Model for extraction checks
                        </p>
                      </div>
                      <div>
                        <label className="text-sm font-medium mb-2 block text-slate-700">Generation Model</label>
                        <Input
                          type="text"
                          value={config.llm_config?.generation_model_name || ""}
                          onChange={(e) => updateLLMConfig({ generation_model_name: e.target.value || undefined })}
                          placeholder="e.g., gpt-5"
                          className="h-10"
                        />
                        <p className="text-xs text-slate-500 mt-1">
                          Model for generation & evaluation
                        </p>
                      </div>
                      <div>
                        <label className="text-sm font-medium mb-2 block text-slate-700">Embedding Model</label>
                        <Input
                          type="text"
                          value={config.llm_config?.embedding_model_name || ""}
                          onChange={(e) => updateLLMConfig({ embedding_model_name: e.target.value || undefined })}
                          placeholder="e.g., text-embedding-3-small"
                          className="h-10"
                        />
                        <p className="text-xs text-slate-500 mt-1">
                          Model for embeddings
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>
            </div>
          )}

          {/* Extractor Settings Tab Content */}
          {activeTab === "extractors" && (
            <div className="space-y-6">{/* Extractor Settings Content */}

            {/* Profile Extractors */}
            <Card className="border-slate-200 bg-white overflow-hidden hover:shadow-lg transition-all duration-300">
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg">
                      <Settings className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <CardTitle className="flex items-center gap-2 text-lg font-semibold text-slate-800">
                        Profile Extractors
                        {config.profile_extractor_configs.length > 0 && (
                          <Badge className="text-xs bg-purple-100 text-purple-700 hover:bg-purple-100">
                            {config.profile_extractor_configs.length}
                          </Badge>
                        )}
                      </CardTitle>
                      <CardDescription className="text-xs mt-1 text-slate-500">Define profile extraction rules</CardDescription>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {config.profile_extractor_configs.map((extractor, index) => (
                  <div key={extractor.id} className="p-5 border rounded-lg space-y-4 bg-muted/30">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-primary">Extractor #{index + 1}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeProfileExtractor(extractor.id)}
                        className="h-8 w-8 p-0"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">Extractor Name</label>
                      <div className="flex gap-3 items-center">
                        <Input
                          value={extractor.extractor_name}
                          onChange={(e) => updateProfileExtractor(extractor.id, { extractor_name: e.target.value })}
                          placeholder="e.g., user_preferences"
                          className="h-10 text-sm flex-1"
                        />
                        <button
                          type="button"
                          onClick={() => updateProfileExtractor(extractor.id, { manual_trigger: !extractor.manual_trigger })}
                          className={`h-10 px-3 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 border whitespace-nowrap ${
                            extractor.manual_trigger
                              ? "bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100"
                              : "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100"
                          }`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${extractor.manual_trigger ? "bg-amber-500" : "bg-emerald-500"}`} />
                          {extractor.manual_trigger ? "Manual" : "Auto"}
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">Profile Content Definition</label>
                      <textarea
                        value={extractor.profile_content_definition_prompt}
                        onChange={(e) => updateProfileExtractor(extractor.id, { profile_content_definition_prompt: e.target.value })}
                        className="flex min-h-[150px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
                        placeholder="Define what the profile should contain..."
                        rows={6}
                      />
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="text-sm font-medium mb-2 block">Context (Optional)</label>
                        <textarea
                          value={extractor.context_prompt || ""}
                          onChange={(e) => updateProfileExtractor(extractor.id, { context_prompt: e.target.value })}
                          className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
                          placeholder="Additional context..."
                          rows={5}
                        />
                      </div>

                      <div>
                        <label className="text-sm font-medium mb-2 block">Metadata (Optional)</label>
                        <textarea
                          value={extractor.metadata_definition_prompt || ""}
                          onChange={(e) => updateProfileExtractor(extractor.id, { metadata_definition_prompt: e.target.value })}
                          className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
                          placeholder="Metadata structure..."
                          rows={5}
                        />
                      </div>
                    </div>

                    {/* Request Sources */}
                    <div>
                      <label className="text-sm font-medium mb-3 block">
                        Enabled Request Sources (Optional)
                      </label>
                      <p className="text-xs text-muted-foreground mb-3">
                        Specify which request sources should trigger profile extraction. Leave empty to enable all sources.
                      </p>
                      <div className="flex gap-3 mb-3">
                        <Input
                          placeholder="Add source name (e.g., api, webhook, manual)"
                          className="h-10 text-sm"
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && e.currentTarget.value.trim()) {
                              addRequestSourceToExtractor(extractor.id, e.currentTarget.value.trim())
                              e.currentTarget.value = ""
                            }
                          }}
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            const input = e.currentTarget.previousElementSibling as HTMLInputElement
                            if (input && input.value.trim()) {
                              addRequestSourceToExtractor(extractor.id, input.value.trim())
                              input.value = ""
                            }
                          }}
                          className="h-10 w-10 p-0"
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {extractor.request_sources_enabled && extractor.request_sources_enabled.length > 0 ? (
                          extractor.request_sources_enabled.map((source, sourceIndex) => (
                            <Badge key={sourceIndex} variant="secondary" className="text-sm h-7 px-3">
                              {source}
                              <button
                                onClick={() => removeRequestSourceFromExtractor(extractor.id, sourceIndex)}
                                className="ml-2 hover:text-destructive"
                              >
                                ×
                              </button>
                            </Badge>
                          ))
                        ) : (
                          <p className="text-xs text-muted-foreground italic">All sources enabled (default)</p>
                        )}
                      </div>
                    </div>

                    {/* Extraction Window Overrides */}
                    <div>
                      <label className="text-sm font-medium mb-3 block">
                        Extraction Window Overrides (Optional)
                      </label>
                      <p className="text-xs text-muted-foreground mb-3">
                        Override global extraction window settings for this extractor. Leave empty to use global settings.
                      </p>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <label className="text-sm font-medium mb-2 block">Window Size Override</label>
                          <Input
                            type="number"
                            min="1"
                            value={extractor.extraction_window_size_override ?? ""}
                            onChange={(e) => updateProfileExtractor(extractor.id, {
                              extraction_window_size_override: e.target.value ? parseInt(e.target.value) : undefined
                            })}
                            placeholder="Use global setting"
                            className="h-10 text-sm"
                          />
                        </div>
                        <div>
                          <label className="text-sm font-medium mb-2 block">Window Stride Override</label>
                          <Input
                            type="number"
                            min="1"
                            value={extractor.extraction_window_stride_override ?? ""}
                            onChange={(e) => updateProfileExtractor(extractor.id, {
                              extraction_window_stride_override: e.target.value ? parseInt(e.target.value) : undefined
                            })}
                            placeholder="Use global setting"
                            className="h-10 text-sm"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                <Button onClick={addProfileExtractor} variant="outline" className="w-full h-9 text-sm">
                  <Plus className="h-3.5 w-3.5 mr-2" />
                  Add Profile Extractor
                </Button>
              </CardContent>
            </Card>

            {/* Agent Feedback */}
            <Card className="border-slate-200 bg-white overflow-hidden hover:shadow-lg transition-all duration-300">
              <CardHeader className="pb-4">
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center shadow-lg">
                    <MessageSquare className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="flex items-center gap-2 text-lg font-semibold text-slate-800">
                      Agent Feedback
                      {config.agent_feedback_configs.length > 0 && (
                        <Badge className="text-xs bg-orange-100 text-orange-700 hover:bg-orange-100">
                          {config.agent_feedback_configs.length}
                        </Badge>
                      )}
                    </CardTitle>
                    <CardDescription className="text-xs mt-1 text-slate-500">Configure feedback collection</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {config.agent_feedback_configs.map((feedback, index) => (
                  <div key={feedback.id} className="p-5 border rounded-lg space-y-4 bg-muted/30">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-primary">Feedback #{index + 1}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeAgentFeedback(feedback.id)}
                        className="h-8 w-8 p-0"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">Feedback Name</label>
                      <Input
                        value={feedback.feedback_name}
                        onChange={(e) => updateAgentFeedback(feedback.id, { feedback_name: e.target.value })}
                        placeholder="e.g., task_completion"
                        className="h-10 text-sm"
                      />
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">Feedback Definition</label>
                      <textarea
                        value={feedback.feedback_definition_prompt}
                        onChange={(e) => updateAgentFeedback(feedback.id, { feedback_definition_prompt: e.target.value })}
                        className="flex min-h-[150px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
                        placeholder="Define what success looks like..."
                        rows={6}
                      />
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">Metadata (Optional)</label>
                      <textarea
                        value={feedback.metadata_definition_prompt || ""}
                        onChange={(e) => updateAgentFeedback(feedback.id, { metadata_definition_prompt: e.target.value })}
                        className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
                        placeholder="Metadata structure..."
                        rows={5}
                      />
                    </div>

                    {/* Request Sources */}
                    <div>
                      <label className="text-sm font-medium mb-3 block">
                        Enabled Request Sources (Optional)
                      </label>
                      <p className="text-xs text-muted-foreground mb-3">
                        Specify which request sources should trigger feedback extraction. Leave empty to enable all sources.
                      </p>
                      <div className="flex gap-3 mb-3">
                        <Input
                          placeholder="Add source name (e.g., api, webhook, manual)"
                          className="h-10 text-sm"
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && e.currentTarget.value.trim()) {
                              addRequestSourceToFeedback(feedback.id, e.currentTarget.value.trim())
                              e.currentTarget.value = ""
                            }
                          }}
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            const input = e.currentTarget.previousElementSibling as HTMLInputElement
                            if (input && input.value.trim()) {
                              addRequestSourceToFeedback(feedback.id, input.value.trim())
                              input.value = ""
                            }
                          }}
                          className="h-10 w-10 p-0"
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {feedback.request_sources_enabled && feedback.request_sources_enabled.length > 0 ? (
                          feedback.request_sources_enabled.map((source, sourceIndex) => (
                            <Badge key={sourceIndex} variant="secondary" className="text-sm h-7 px-3">
                              {source}
                              <button
                                onClick={() => removeRequestSourceFromFeedback(feedback.id, sourceIndex)}
                                className="ml-2 hover:text-destructive"
                              >
                                ×
                              </button>
                            </Badge>
                          ))
                        ) : (
                          <p className="text-xs text-muted-foreground italic">All sources enabled (default)</p>
                        )}
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="text-sm font-medium mb-2 block">Min Feedback Threshold</label>
                        <Input
                          type="number"
                          min="1"
                          value={feedback.feedback_aggregator_config?.min_feedback_threshold || 2}
                          onChange={(e) => updateAgentFeedback(feedback.id, {
                            feedback_aggregator_config: {
                              min_feedback_threshold: parseInt(e.target.value) || 2,
                              refresh_count: feedback.feedback_aggregator_config?.refresh_count ?? 2
                            }
                          })}
                          className="h-10 text-sm"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          Min number of feedbacks per cluster
                        </p>
                      </div>

                      <div>
                        <label className="text-sm font-medium mb-2 block">Refresh Count</label>
                        <Input
                          type="number"
                          min="1"
                          value={feedback.feedback_aggregator_config?.refresh_count || 2}
                          onChange={(e) => updateAgentFeedback(feedback.id, {
                            feedback_aggregator_config: {
                              min_feedback_threshold: feedback.feedback_aggregator_config?.min_feedback_threshold ?? 2,
                              refresh_count: parseInt(e.target.value) || 2
                            }
                          })}
                          className="h-10 text-sm"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          Number of new feedbacks to trigger feedback aggregation
                        </p>
                      </div>
                    </div>

                    {/* Extraction Window Overrides */}
                    <div>
                      <label className="text-sm font-medium mb-3 block">
                        Extraction Window Overrides (Optional)
                      </label>
                      <p className="text-xs text-muted-foreground mb-3">
                        Override global extraction window settings for this feedback extractor. Leave empty to use global settings.
                      </p>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <label className="text-sm font-medium mb-2 block">Window Size Override</label>
                          <Input
                            type="number"
                            min="1"
                            value={feedback.extraction_window_size_override ?? ""}
                            onChange={(e) => updateAgentFeedback(feedback.id, {
                              extraction_window_size_override: e.target.value ? parseInt(e.target.value) : undefined
                            })}
                            placeholder="Use global setting"
                            className="h-10 text-sm"
                          />
                        </div>
                        <div>
                          <label className="text-sm font-medium mb-2 block">Window Stride Override</label>
                          <Input
                            type="number"
                            min="1"
                            value={feedback.extraction_window_stride_override ?? ""}
                            onChange={(e) => updateAgentFeedback(feedback.id, {
                              extraction_window_stride_override: e.target.value ? parseInt(e.target.value) : undefined
                            })}
                            placeholder="Use global setting"
                            className="h-10 text-sm"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                <Button onClick={addAgentFeedback} variant="outline" className="w-full h-9 text-sm">
                  <Plus className="h-3.5 w-3.5 mr-2" />
                  Add Agent Feedback
                </Button>
              </CardContent>
            </Card>

            {/* Agent Success */}
            <Card className="border-slate-200 bg-white overflow-hidden hover:shadow-lg transition-all duration-300">
              <CardHeader className="pb-4">
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-lg">
                    <CheckCircle className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="flex items-center gap-2 text-lg font-semibold text-slate-800">
                      Agent Success Evaluations
                      {config.agent_success_configs.length > 0 && (
                        <Badge className="text-xs bg-emerald-100 text-emerald-700 hover:bg-emerald-100">
                          {config.agent_success_configs.length}
                        </Badge>
                      )}
                    </CardTitle>
                    <CardDescription className="text-xs mt-1 text-slate-500">Define success criteria</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {config.agent_success_configs.map((success, index) => (
                  <div key={success.id} className="p-5 border rounded-lg space-y-4 bg-muted/30">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-primary">Success #{index + 1}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeAgentSuccess(success.id)}
                        className="h-8 w-8 p-0"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">Evaluation Name</label>
                      <Input
                        value={success.evaluation_name}
                        onChange={(e) => updateAgentSuccess(success.id, { evaluation_name: e.target.value })}
                        placeholder="e.g., task_success"
                        className="h-10 text-sm"
                      />
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">Success Definition</label>
                      <textarea
                        value={success.success_definition_prompt}
                        onChange={(e) => updateAgentSuccess(success.id, { success_definition_prompt: e.target.value })}
                        className="flex min-h-[150px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
                        placeholder="Define what success looks like for the agent..."
                        rows={6}
                      />
                    </div>

                    {/* Sampling Rate */}
                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        Sampling Rate
                        <span className="text-xs text-muted-foreground ml-2 font-normal">
                          Percentage of interaction batches to evaluate
                        </span>
                      </label>
                      <div className="grid grid-cols-3 gap-3 items-center">
                        <div className="col-span-2">
                          <input
                            type="range"
                            min="0"
                            max="100"
                            value={((success.sampling_rate ?? 1.0) * 100).toFixed(0)}
                            onChange={(e) => updateAgentSuccess(success.id, { sampling_rate: parseFloat(e.target.value) / 100 })}
                            className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
                          />
                        </div>
                        <div className="relative">
                          <Input
                            type="number"
                            min="0"
                            max="100"
                            step="1"
                            value={((success.sampling_rate ?? 1.0) * 100).toFixed(0)}
                            onChange={(e) => {
                              const value = parseFloat(e.target.value)
                              if (!isNaN(value) && value >= 0 && value <= 100) {
                                updateAgentSuccess(success.id, { sampling_rate: value / 100 })
                              }
                            }}
                            className="h-10 text-sm pr-8"
                          />
                          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground pointer-events-none">
                            %
                          </span>
                        </div>
                      </div>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">Metadata (Optional)</label>
                      <textarea
                        value={success.metadata_definition_prompt || ""}
                        onChange={(e) => updateAgentSuccess(success.id, { metadata_definition_prompt: e.target.value })}
                        className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
                        placeholder="Metadata structure..."
                        rows={5}
                      />
                    </div>

                    {/* Tools */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <label className="text-sm font-medium">Available Tools</label>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => addToolToSuccess(success.id)}
                          className="h-8 text-sm"
                        >
                          <Plus className="h-4 w-4 mr-1" />
                          Add
                        </Button>
                      </div>
                      <div className="space-y-3">
                        {success.tool_can_use?.map((tool, toolIndex) => (
                          <div key={toolIndex} className="flex gap-3 items-center p-3 border rounded bg-background/50">
                            <div className="flex-1 grid grid-cols-2 gap-3">
                              <Input
                                value={tool.tool_name}
                                onChange={(e) => updateToolInSuccess(success.id, toolIndex, { tool_name: e.target.value })}
                                placeholder="Tool name"
                                className="h-10 text-sm"
                              />
                              <Input
                                value={tool.tool_description}
                                onChange={(e) => updateToolInSuccess(success.id, toolIndex, { tool_description: e.target.value })}
                                placeholder="Description"
                                className="h-10 text-sm"
                              />
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeToolFromSuccess(success.id, toolIndex)}
                              className="h-8 w-8 p-0"
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Action Space */}
                    <div>
                      <label className="text-sm font-medium mb-3 block">Action Space</label>
                      <div className="flex gap-3 mb-3">
                        <Input
                          placeholder="Add action"
                          className="h-10 text-sm"
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && e.currentTarget.value.trim()) {
                              addActionToSuccess(success.id, e.currentTarget.value.trim())
                              e.currentTarget.value = ""
                            }
                          }}
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            const input = e.currentTarget.previousElementSibling as HTMLInputElement
                            if (input && input.value.trim()) {
                              addActionToSuccess(success.id, input.value.trim())
                              input.value = ""
                            }
                          }}
                          className="h-10 w-10 p-0"
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {success.action_space?.map((action, actionIndex) => (
                          <Badge key={actionIndex} variant="secondary" className="text-sm h-7 px-3">
                            {action}
                            <button
                              onClick={() => removeActionFromSuccess(success.id, actionIndex)}
                              className="ml-2 hover:text-destructive"
                            >
                              ×
                            </button>
                          </Badge>
                        ))}
                      </div>
                    </div>

                    {/* Extraction Window Overrides */}
                    <div>
                      <label className="text-sm font-medium mb-3 block">
                        Extraction Window Overrides (Optional)
                      </label>
                      <p className="text-xs text-muted-foreground mb-3">
                        Override global extraction window settings for this success evaluator. Leave empty to use global settings.
                      </p>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <label className="text-sm font-medium mb-2 block">Window Size Override</label>
                          <Input
                            type="number"
                            min="1"
                            value={success.extraction_window_size_override ?? ""}
                            onChange={(e) => updateAgentSuccess(success.id, {
                              extraction_window_size_override: e.target.value ? parseInt(e.target.value) : undefined
                            })}
                            placeholder="Use global setting"
                            className="h-10 text-sm"
                          />
                        </div>
                        <div>
                          <label className="text-sm font-medium mb-2 block">Window Stride Override</label>
                          <Input
                            type="number"
                            min="1"
                            value={success.extraction_window_stride_override ?? ""}
                            onChange={(e) => updateAgentSuccess(success.id, {
                              extraction_window_stride_override: e.target.value ? parseInt(e.target.value) : undefined
                            })}
                            placeholder="Use global setting"
                            className="h-10 text-sm"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                <Button onClick={addAgentSuccess} variant="outline" className="w-full h-9 text-sm">
                  <Plus className="h-3.5 w-3.5 mr-2" />
                  Add Success Evaluation
                </Button>
              </CardContent>
            </Card>
            </div>
          )}

          {/* Workflow Visualization Tab Content */}
          {activeTab === "workflow" && (
            <div className="space-y-6">
              <Card className="border-slate-200 bg-white overflow-hidden hover:shadow-lg transition-all duration-300">
                <CardHeader className="pb-4">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg">
                      <Workflow className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <CardTitle className="text-lg font-semibold text-slate-800">Reflexio Workflow</CardTitle>
                      <CardDescription className="text-xs mt-1 text-slate-500">
                        Visual representation of how your configuration processes data
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="mb-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
                    <p className="text-sm text-slate-600">
                      This diagram shows how requests flow through the Reflexio system based on your current configuration.
                      Click on nodes to view detailed information about each component.
                    </p>
                  </div>
                  <WorkflowVisualization config={config} />
                </CardContent>
              </Card>
            </div>
          )}

          {/* Bottom Save Button */}
          <div className="mt-8 flex justify-end items-center gap-3">
            {hasUnsavedChanges && (
              <span className="text-xs text-amber-600 font-medium flex items-center gap-1.5 bg-amber-50 px-3 py-1.5 rounded-lg border border-amber-200">
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                Unsaved changes
              </span>
            )}
            <Button onClick={handleSave} disabled={saveStatus === "saving"} size="lg" className={`shadow-lg border-0 ${hasUnsavedChanges ? "shadow-amber-500/25 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600" : "shadow-indigo-500/25 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"}`}>
              <Save className="h-4 w-4 mr-2" />
              {saveStatus === "saving" ? "Saving..." : "Save Configuration"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
