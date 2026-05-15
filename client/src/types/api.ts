// HTTP types mirror the OpenAPI spec under /spec/openapi.yaml. When the spec
// changes, update here in lockstep. (Codegen from the spec is a future step.)

export type TokenPair = {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresIn: number
}

export type Account = {
  id: string
  email: string
  createdAt: string
}

export type Player = {
  id: string
  accountId: string
  name: string
  description?: string | null
  currentRoomId: string
  inventoryItemIds: string[]
  createdAt: string
  lastSeenAt?: string | null
}
