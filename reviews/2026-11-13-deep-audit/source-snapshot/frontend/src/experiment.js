export function trialTimeLeft(assignment, startedAt, now) {
  if (!startedAt) return assignment.time_limit_seconds
  return Math.max(0, Math.ceil(assignment.time_limit_seconds - (now - Date.parse(startedAt)) / 1000))
}

export function clockLabel(seconds) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function nextTrialIndex(assignment) {
  return assignment.trial_index < 4 ? assignment.trial_index + 1 : null
}
