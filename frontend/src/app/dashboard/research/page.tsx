"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Shell } from "@/components/layout"
import { Button, Card } from "@/components/ui"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { useResearchTasks } from "@/hooks/useResearchTasks"
import { Clock, CheckCircle, AlertCircle, Loader, Plus, Trash2 } from "lucide-react"

export default function ResearchPage() {
  const router = useRouter()
  const [page, setPage] = useState(1)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const { data, loading, error, refetch } = useResearchTasks(page, 10)

  const handleDelete = async (e: React.MouseEvent, taskId: string) => {
    e.stopPropagation()  // Prevent navigation when clicking delete
    
    if (!confirm("Are you sure you want to delete this research task? This action cannot be undone.")) {
      return
    }

    setDeletingId(taskId)
    try {
      const token = localStorage.getItem("consilience_access_token")
      if (!token) throw new Error("Not authenticated")

      const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
      const response = await fetch(`${apiUrl}/api/research/${taskId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({
          detail: "Unknown error occurred",
        }))
        const errorMessage = errorData.detail || errorData.message || "Unknown error occurred"
        alert(`Failed to delete task: ${errorMessage}`)
        return
      }

      // Refresh the task list
      await refetch()
    } catch (err) {
      console.error("Delete error:", err)
      alert("Failed to delete task. Please try again.")
    } finally {
      setDeletingId(null)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case "running":
        return <Loader className="h-5 w-5 text-blue-500 animate-spin" />
      case "pending":
        return <Clock className="h-5 w-5 text-yellow-500" />
      case "failed":
      case "cancelled":
        return <AlertCircle className="h-5 w-5 text-red-500" />
      default:
        return <Clock className="h-5 w-5 text-gray-500" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
      case "running":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
      case "pending":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
      case "failed":
      case "cancelled":
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200"
    }
  }

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString)
      if (Number.isNaN(date.getTime())) {
        return dateString
      }
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    } catch {
      return dateString
    }
  }

  return (
    <ProtectedRoute>
      <Shell>
        <div className="w-full max-w-[1200px] mx-auto space-y-6">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="space-y-2">
              <h1 className="text-3xl md:text-4xl" style={{ fontFamily: "var(--font-display)", fontWeight: 400 }}>
                Research Tasks
              </h1>
              <p className="text-[var(--text-secondary)]">
                View and manage all your research tasks
              </p>
            </div>
            <Button
              onClick={() => router.push("/dashboard/research/new")}
              className="w-full md:w-auto"
            >
              <Plus className="h-4 w-4 mr-2" />
              New Research
            </Button>
          </div>

          {/* Error State */}
          {error && (
            <Card className="p-4 border-red-200 bg-red-50 dark:bg-red-950">
              <p className="text-red-800 dark:text-red-200">Error: {error}</p>
              <Button
                onClick={() => void refetch()}
                variant="secondary"
                className="mt-3"
              >
                Retry
              </Button>
            </Card>
          )}

          {/* Loading State */}
          {loading && !data && (
            <div className="flex items-center justify-center py-12">
              <div className="space-y-4 text-center">
                <Loader className="h-8 w-8 animate-spin mx-auto text-[var(--text-secondary)]" />
                <p className="text-[var(--text-secondary)]">Loading research tasks...</p>
              </div>
            </div>
          )}

          {/* Empty State */}
          {data && data.tasks.length === 0 && (
            <Card className="p-12 text-center">
              <div className="space-y-4">
                <p className="text-[var(--text-secondary)] text-lg">
                  No research tasks yet
                </p>
                <p className="text-[var(--text-tertiary)]">
                  Create your first research task to get started
                </p>
                <Button
                  onClick={() => router.push("/dashboard/research/new")}
                  className="mt-4"
                >
                  Create First Research
                </Button>
              </div>
            </Card>
          )}

          {/* Task Grid */}
          {data && data.tasks.length > 0 && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4">
                {data.tasks.map((task) => {
                  const handleClick = () => router.push(`/dashboard/research/${task.task_id}`)
                  return (
                  <div
                    key={task.task_id}
                    role="button"
                    tabIndex={0}
                    className="p-4 rounded-lg hover:shadow-md transition-shadow cursor-pointer border border-[var(--border-default)] bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)]"
                    onClick={handleClick}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        handleClick()
                      }
                    }}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          {getStatusIcon(task.status)}
                          <h3 className="font-semibold truncate">{task.title}</h3>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium whitespace-nowrap ${getStatusColor(task.status)}`}>
                            {task.status}
                          </span>
                          <span className="px-2 py-1 rounded-full text-xs font-medium bg-[var(--bg-hover)] text-[var(--text-secondary)]">
                            {task.depth}
                          </span>
                        </div>
                        <p className="text-sm text-[var(--text-secondary)] line-clamp-2 mb-3">
                          {task.description}
                        </p>
                        <div className="flex flex-wrap gap-4 text-xs text-[var(--text-tertiary)]">
                          <div>Created: {formatDate(task.created_at)}</div>
                          {task.completed_at && (
                            <div>Completed: {formatDate(task.completed_at)}</div>
                          )}
                          {task.actual_cost_usd !== null && task.actual_cost_usd !== undefined && (
                            <div>Cost: ${task.actual_cost_usd.toFixed(4)}</div>
                          )}
                          {task.progress_percent > 0 && (
                            <div>Progress: {task.progress_percent}%</div>
                          )}
                        </div>
                      </div>
                      {task.progress_percent > 0 && task.status === "running" && (
                        <div className="w-20">
                          <div className="h-1 bg-[var(--bg-hover)] rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 transition-all"
                              style={{ width: `${task.progress_percent}%` }}
                            />
                          </div>
                          <div className="text-xs text-[var(--text-tertiary)] text-right mt-1">
                            {task.progress_percent}%
                          </div>
                        </div>
                      )}
                      <button
                        onClick={(e) => handleDelete(e, task.task_id)}
                        disabled={deletingId === task.task_id}
                        className="p-2 text-[var(--text-tertiary)] hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Delete task"
                      >
                        {deletingId === task.task_id ? (
                          <Loader className="h-5 w-5 animate-spin" />
                        ) : (
                          <Trash2 className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                  </div>
                  )
                })}
              </div>

              {/* Pagination */}
              {data.total_pages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-6">
                  <Button
                    variant="secondary"
                    disabled={page === 1}
                    onClick={() => setPage(Math.max(1, page - 1))}
                  >
                    Previous
                  </Button>
                  <div className="text-sm text-[var(--text-tertiary)]">
                    Page {data.page} of {data.total_pages}
                  </div>
                  <Button
                    variant="secondary"
                    disabled={page === data.total_pages}
                    onClick={() => setPage(Math.min(data.total_pages, page + 1))}
                  >
                    Next
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </Shell>
    </ProtectedRoute>
  )
}
