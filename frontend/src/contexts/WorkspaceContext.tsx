import { createContext, useContext, type ReactNode } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useAuth } from './AuthContext';
import { workspacesApi, workspaceMembersApi } from '../api/client';
import type { Workspace, WorkspaceMember } from '../types';

interface WorkspaceContextValue {
  workspace: Workspace | null;
  workspaces: Workspace[];
  currentMembership: WorkspaceMember | null;
  userRole: string | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  switchWorkspace: (id: number) => Promise<void>;
  createWorkspace: (name: string) => Promise<Workspace>;
  deleteWorkspace: (id: number) => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const {
    data: workspace,
    isLoading: workspaceLoading,
    error: workspaceError,
    refetch: refetchWorkspace,
  } = useQuery({
    queryKey: ['workspace-current'],
    queryFn: workspacesApi.getCurrent,
    enabled: isAuthenticated,
  });

  const {
    data: workspaces = [],
    isLoading: workspacesLoading,
    refetch: refetchWorkspaces,
  } = useQuery({
    queryKey: ['workspaces'],
    queryFn: workspacesApi.list,
    enabled: isAuthenticated,
  });

  const {
    data: members,
    isLoading: membersLoading,
    error: membersError,
    refetch: refetchMembers,
  } = useQuery({
    queryKey: ['workspace-members', workspace?.id],
    queryFn: () => workspaceMembersApi.list(workspace!.id),
    enabled: !!workspace?.id,
  });

  const currentMembership = members?.find(m => m.user_id === user?.id) || null;
  const userRole = currentMembership?.role || null;

  const switchMutation = useMutation({
    mutationFn: (workspaceId: number) => workspacesApi.switch(workspaceId),
    onSuccess: () => {
      queryClient.invalidateQueries();
      localStorage.removeItem('monie_selected_account');
    },
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => workspacesApi.create({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries();
      localStorage.removeItem('monie_selected_account');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (workspaceId: number) => workspacesApi.delete(workspaceId),
    onSuccess: () => {
      queryClient.invalidateQueries();
      localStorage.removeItem('monie_selected_account');
    },
  });

  const switchWorkspace = async (id: number) => {
    await switchMutation.mutateAsync(id);
  };

  const createWorkspace = async (name: string): Promise<Workspace> => {
    const ws = await createMutation.mutateAsync(name);
    return ws;
  };

  const deleteWorkspace = async (id: number) => {
    await deleteMutation.mutateAsync(id);
  };

  const refetch = () => {
    refetchWorkspace();
    refetchWorkspaces();
    refetchMembers();
  };

  return (
    <WorkspaceContext.Provider
      value={{
        workspace: workspace || null,
        workspaces,
        currentMembership,
        userRole,
        isLoading: workspaceLoading || membersLoading || workspacesLoading,
        error: (workspaceError || membersError) as Error | null,
        refetch,
        switchWorkspace,
        createWorkspace,
        deleteWorkspace,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (context === undefined) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }
  return context;
}
