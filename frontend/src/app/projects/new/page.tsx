/**
 * projects/new/page.tsx — Create a new ReqLens project.
 *
 * Form with three fields:
 *   1. Project name (unique identifier)
 *   2. Code path (absolute filesystem path to the codebase)
 *   3. Requirements path (absolute path to the requirements document)
 *
 * On successful creation, redirects to the new project's detail page.
 * The code path field includes a real-time validation check via the
 * /api/v1/fs/validate endpoint to confirm the path exists on the server.
 *
 * Design: single-column form in a card, matching the spec's "verbs, no marketing"
 * button style — "Create project" not "Get Started".
 */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert } from '@/components/ui/alert';
import { FolderPlus, CircleCheck, CircleX, Loader2 } from 'lucide-react';

export default function NewProjectPage() {
  const router = useRouter();

  // Form field state
  const [name, setName] = useState('');
  const [codePath, setCodePath] = useState('');
  const [reqPath, setReqPath] = useState('');

  // Submission state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Path validation state — checked on blur
  const [codePathValid, setCodePathValid] = useState<boolean | null>(null);
  const [reqPathValid, setReqPathValid] = useState<boolean | null>(null);

  /**
   * Validate a filesystem path by calling the backend's /fs/validate endpoint.
   * Updates the corresponding validation state (code or requirements path).
   */
  const validatePath = async (path: string, setter: (v: boolean | null) => void) => {
    if (!path.trim()) {
      setter(null);
      return;
    }
    try {
      const result = await api.validatePath(path);
      setter(result.exists);
    } catch {
      setter(null);
    }
  };

  /**
   * Handle form submission — create the project via the API and redirect
   * to its detail page on success. Shows an error message on failure.
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const project = await api.createProject({
        name,
        code_path: codePath,
        requirements_path: reqPath,
      });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      {/* ---- Page header ---- */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">New Project</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Register a codebase and its requirements document for analysis.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FolderPlus className="h-4 w-4" />
            Project details
          </CardTitle>
          <CardDescription>
            Provide the project name and absolute filesystem paths.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* ---- Project name field ---- */}
            <div className="space-y-2">
              <Label htmlFor="name">Project name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="my-project"
                required
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Must be unique across all projects.
              </p>
            </div>

            {/* ---- Code path field with validation indicator ---- */}
            <div className="space-y-2">
              <Label htmlFor="code_path">Code directory</Label>
              <div className="relative">
                <Input
                  id="code_path"
                  value={codePath}
                  onChange={(e) => {
                    setCodePath(e.target.value);
                    setCodePathValid(null); // Reset validation on change
                  }}
                  onBlur={() => validatePath(codePath, setCodePathValid)}
                  placeholder="/absolute/path/to/code"
                  required
                  className="font-mono text-sm pr-8"
                />
                {/* Real-time path validation indicator */}
                <PathValidationIcon valid={codePathValid} />
              </div>
              <p className="text-xs text-muted-foreground">
                Absolute path to the project&apos;s source code directory.
              </p>
            </div>

            {/* ---- Requirements path field with validation indicator ---- */}
            <div className="space-y-2">
              <Label htmlFor="req_path">Requirements document</Label>
              <div className="relative">
                <Input
                  id="req_path"
                  value={reqPath}
                  onChange={(e) => {
                    setReqPath(e.target.value);
                    setReqPathValid(null);
                  }}
                  onBlur={() => validatePath(reqPath, setReqPathValid)}
                  placeholder="/absolute/path/to/requirements.md"
                  required
                  className="font-mono text-sm pr-8"
                />
                <PathValidationIcon valid={reqPathValid} />
              </div>
              <p className="text-xs text-muted-foreground">
                Absolute path to the requirements document (Markdown).
              </p>
            </div>

            {/* ---- Error message ---- */}
            {error && (
              <Alert variant="destructive" className="text-sm">
                {error}
              </Alert>
            )}

            {/* ---- Submit button ---- */}
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create project'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper Components
// ---------------------------------------------------------------------------

/**
 * PathValidationIcon — Shows a check/x icon inside the input field
 * to indicate whether the entered filesystem path exists on the server.
 */
function PathValidationIcon({ valid }: { valid: boolean | null }) {
  if (valid === null) return null;
  return (
    <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
      {valid ? (
        <CircleCheck className="h-4 w-4 text-emerald-500" />
      ) : (
        <CircleX className="h-4 w-4 text-rose-500" />
      )}
    </div>
  );
}
