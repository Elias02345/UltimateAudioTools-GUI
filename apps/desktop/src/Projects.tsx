import { useState } from "react";
import {
  Archive,
  ArrowRight,
  FolderOpen,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { api } from "./api";
import type { Job, Project } from "./api";
import { Empty } from "./components";

export function Projects({
  projects,
  jobs,
  onChange,
  onOpen,
  onDelete,
  onError,
}: {
  projects: Project[];
  jobs: Job[];
  onChange: (projects: Project[]) => void;
  onOpen: (id: string) => void;
  onDelete: (project: Project) => void;
  onError: (error: unknown) => void;
}) {
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [rename, setRename] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const mutate = async (method: string, params: Record<string, unknown>) => {
    setBusy(true);
    try {
      const updated = await api<Project[]>(method, params);
      onChange(updated);
      return updated;
    } catch (error) {
      onError(error);
      return null;
    } finally {
      setBusy(false);
    }
  };
  const visible = projects.filter(
    (p) =>
      p.archived === showArchived &&
      p.name.toLowerCase().includes(query.toLowerCase()),
  );
  const unfiled = jobs.filter(
    (j) => !j.project_id && j.status === "Completed",
  ).length;
  return (
    <section className="projects-view">
      <div className="page-heading">
        <div>
          <h1>A place for every recording.</h1>
          <p>
            Group your generations into projects. Archive finished work to keep
            your studio tidy.
          </p>
        </div>
      </div>
      <form
        className="project-create"
        onSubmit={(e) => {
          e.preventDefault();
          void mutate("create_project", { name }).then((updated) => {
            if (updated) {
              setName("");
              setShowArchived(false);
            }
          });
        }}
      >
        <label>
          New project
          <input
            maxLength={100}
            value={name}
            placeholder="Album, track or session name"
            onChange={(e) => setName(e.target.value)}
            disabled={busy}
          />
        </label>
        <button className="primary" disabled={busy || !name.trim()}>
          <Plus size={16} /> Create project
        </button>
      </form>
      <div className="project-toolbar">
        <label>
          Find a project
          <input
            aria-label="Search projects"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search projects…"
          />
        </label>
        <div className="result-mode" role="group" aria-label="Project status">
          <button
            aria-pressed={!showArchived}
            className={!showArchived ? "active" : ""}
            onClick={() => setShowArchived(false)}
          >
            Active
          </button>
          <button
            aria-pressed={showArchived}
            className={showArchived ? "active" : ""}
            onClick={() => setShowArchived(true)}
          >
            Archived
          </button>
        </div>
      </div>
      <div className="project-list">
        {visible.map((project) => {
          const entries = jobs.filter((j) => j.project_id === project.id);
          const completed = entries.filter(
            (j) => j.status === "Completed",
          ).length;
          return (
            <div
              className="project-row"
              key={project.id}
              data-project-id={project.id}
            >
              <FolderOpen size={20} />
              <div className="project-info">
                {editing === project.id ? (
                  <form
                    className="project-rename"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void mutate("rename_project", {
                        id: project.id,
                        name: rename,
                      }).then((updated) => {
                        if (updated) setEditing(null);
                      });
                    }}
                  >
                    <input
                      aria-label="Project name"
                      maxLength={100}
                      value={rename}
                      onChange={(e) => setRename(e.target.value)}
                      autoFocus
                    />
                    <button disabled={busy || !rename.trim()}>Save name</button>
                    <button type="button" onClick={() => setEditing(null)}>
                      Cancel
                    </button>
                  </form>
                ) : (
                  <>
                    <strong>{project.name}</strong>
                    <small>
                      {completed} {completed === 1 ? "result" : "results"} ·{" "}
                      {entries.length} generations
                      {project.archived ? " · Archived" : ""}
                    </small>
                  </>
                )}
              </div>
              <div className="actions">
                <button onClick={() => onOpen(project.id)}>
                  Open project <ArrowRight size={14} />
                </button>
                <button
                  aria-label={`Rename ${project.name}`}
                  disabled={busy}
                  onClick={() => {
                    setEditing(project.id);
                    setRename(project.name);
                  }}
                >
                  <Pencil size={15} />
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    void mutate("archive_project", {
                      id: project.id,
                      archived: !project.archived,
                    })
                  }
                >
                  <Archive size={15} />
                  {project.archived ? "Restore" : "Archive"}
                </button>
                <button
                  aria-label={`Remove project ${project.name}`}
                  disabled={busy}
                  onClick={() => onDelete(project)}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
      {!visible.length && (
        <Empty
          title={
            query
              ? "No matching projects"
              : showArchived
                ? "Your archive is empty"
                : "Start with a project"
          }
        >
          {query
            ? "Try another name."
            : showArchived
              ? "Archived projects keep their results and can be restored anytime."
              : "Create a project above, then move existing results into it or choose it before separating."}
        </Empty>
      )}
      <button className="text-button" onClick={() => onOpen("unfiled")}>
        View unfiled results ({unfiled}) <ArrowRight size={14} />
      </button>
    </section>
  );
}
