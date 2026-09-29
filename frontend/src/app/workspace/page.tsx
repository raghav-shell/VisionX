import WorkspaceStudio from "@/components/workspace/WorkspaceStudio";

export const metadata = {
  title: "VisionX Workspace — Assurance Review",
  description: "Offline workspace for reviewing VisionSentinel findings, coverage, detector execution, evidence, and scan reports.",
};

export default function WorkspacePage() {
  return <WorkspaceStudio />;
}
