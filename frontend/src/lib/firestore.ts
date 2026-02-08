/**
 * DB operations go through the Flask backend (Firestore). Re-exports from db-api.
 * All functions require a Firebase ID token (from getAccessToken()); no more direct Firestore.
 */
export {
  fetchClassrooms,
  fetchClassroom,
  createClassroom,
  updateClassroom,
  deleteClassroom,
  fetchAssignments,
  fetchAssignment,
  createAssignment,
  updateAssignment,
  deleteAssignment,
  fetchProgress,
  fetchInvitedStudents,
  inviteStudent,
  deleteInvite,
  fetchAssignmentsForUser,
} from "@/lib/db-api";
