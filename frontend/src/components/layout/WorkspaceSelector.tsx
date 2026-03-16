import { useState, useRef, useEffect } from 'react'
import { HiCheck, HiPlus, HiCog, HiOfficeBuilding } from 'react-icons/hi'
import toast from 'react-hot-toast'
import { useWorkspace } from '../../contexts/WorkspaceContext'
import type { Workspace } from '../../types'

interface WorkspaceSelectorProps {
  onOpenSettings: () => void
}

export default function WorkspaceSelector({ onOpenSettings }: WorkspaceSelectorProps) {
  const { workspace, workspaces, switchWorkspace, createWorkspace, isLoading } = useWorkspace()
  const [isOpen, setIsOpen] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setIsCreating(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSwitch = async (ws: Workspace) => {
    if (ws.id === workspace?.id) {
      setIsOpen(false)
      return
    }
    setIsSubmitting(true)
    try {
      await switchWorkspace(ws.id)
      setIsOpen(false)
    } catch (error) {
      console.error('Failed to switch workspace:', error)
      toast.error('Failed to switch workspace')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    setIsSubmitting(true)
    try {
      await createWorkspace(newName.trim())
      setNewName('')
      setIsCreating(false)
      setIsOpen(false)
    } catch (error) {
      console.error('Failed to create workspace:', error)
      toast.error('Failed to create workspace')
    } finally {
      setIsSubmitting(false)
    }
  }

  const getRoleBadge = (ws: Workspace) => {
    const role = ws.user_role
    if (!role) return null
    const colors: Record<string, string> = {
      owner: 'bg-purple-100 text-purple-700',
      admin: 'bg-blue-100 text-blue-700',
      member: 'bg-green-100 text-green-700',
      viewer: 'bg-gray-100 text-gray-700',
    }
    return (
      <span className={`text-xs px-1.5 py-0.5 rounded ${colors[role] || colors.viewer}`}>
        {role}
      </span>
    )
  }

  if (!workspace) {
    return (
      <div className="px-3 py-2">
        <button
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700"
        >
          <HiOfficeBuilding className="h-4 w-4" />
          No workspace
        </button>
      </div>
    )
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        className="flex items-center gap-2 w-full px-3 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors disabled:opacity-50"
      >
        <HiOfficeBuilding className="h-4 w-4 text-gray-600 flex-shrink-0" />
        <span className="text-sm font-medium text-gray-700 truncate flex-1 text-left">
          {workspace.name}
        </span>
        <svg
          className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
          {isCreating ? (
            <div className="p-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Workspace name"
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreate()
                  if (e.key === 'Escape') setIsCreating(false)
                }}
              />
              <div className="flex gap-2 mt-2">
                <button
                  onClick={handleCreate}
                  disabled={!newName.trim() || isSubmitting}
                  className="flex-1 px-2 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  Create
                </button>
                <button
                  onClick={() => setIsCreating(false)}
                  className="px-2 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              {workspaces.map((ws) => (
                <button
                  key={ws.id}
                  onClick={() => handleSwitch(ws)}
                  disabled={isSubmitting}
                  className={`flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${
                    ws.id === workspace?.id ? 'bg-gray-50' : ''
                  }`}
                >
                  {ws.id === workspace?.id ? (
                    <HiCheck className="h-4 w-4 text-blue-600 flex-shrink-0" />
                  ) : (
                    <div className="h-4 w-4" />
                  )}
                  <span className="truncate flex-1 text-left">{ws.name}</span>
                  {getRoleBadge(ws)}
                </button>
              ))}

              <div className="border-t border-gray-100 mt-1 pt-1">
                <button
                  onClick={() => setIsCreating(true)}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  <HiPlus className="h-4 w-4" />
                  Create workspace
                </button>
                <button
                  onClick={() => {
                    setIsOpen(false)
                    onOpenSettings()
                  }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  <HiCog className="h-4 w-4" />
                  Workspace settings
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
