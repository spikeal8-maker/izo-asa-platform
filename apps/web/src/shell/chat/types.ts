import type {
  ChatPolicyView, CredentialView, MessageView, ThreadView,
} from '../../shared/api'

export type ChatPolicy = ChatPolicyView
export type ChatCredential = CredentialView
export type ChatThread = ThreadView
export type ChatMessage = MessageView
export type ChatModel = ChatPolicyView['models'][number]
