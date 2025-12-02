#!/bin/bash

# Update project fields for issues 426-429
# Issue #426 - Portfolio Manager Phase 2
gh api graphql -f query='
mutation {
  updateProjectV2ItemFieldValue(input: {
    projectId: "PVT_kwHOAVnvVs4AvoC8"
    itemId: "PVTI_lAHOAVnvVs4AvoC8zgn29uI"
    fieldId: "PVTF_lAHOAVnvVs4AvoC8zA0"
    value: "P2"
  }) {
    projectV2Item {
      id
    }
  }
}' 2>/dev/null || echo "Note: Direct field updates require specific field IDs from the project board"

echo "Issues assigned and added to project. Manual field updates (Priority, Size, Status) may need to be done via the web UI."
