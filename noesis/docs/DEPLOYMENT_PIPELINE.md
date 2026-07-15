# Future deployment pipeline

Noesis has no selected production environment, registry, ownership model, or release policy.
Accordingly, the repository contains no active deployment workflow. The current manual release
build produces reviewable inputs but publishes nothing.

When those decisions exist, the intended promotion path is:

```text
merge CI -> immutable release build -> human approval -> registry publication
         -> environment promotion -> post-deploy health checks -> rollback decision
```

Each stage should consume the exact digest produced by the preceding stage. Rebuilding during
promotion would destroy provenance. Environment credentials should be short-lived, scoped to one
environment, protected by approvals, and unavailable to pull-request workflows.

## Required decisions before activation

- Deployment target and accountable owner
- Image/package registry and immutable naming convention
- Versioning, changelog, signing, provenance, and retention policy
- Staging and production environment protection rules
- Secrets provider, workload identity, and network policy
- Database/data-volume migration and backup strategy
- Service-level objectives, monitoring, alerting, and rollback triggers
- Incident response and release-approval responsibilities

## Kubernetes mapping (future)

If Kubernetes is selected, the Compose services map conceptually as follows:

- Noesis: a non-root `Deployment`, internal `Service`, liveness `/live`, readiness `/ready`, bounded
  resources, read-only root filesystem where feasible, and a persistent volume mounted at
  `/app/.noesis_data`.
- Redis and Qdrant: managed services where available, otherwise separately owned stateful workloads
  with backups and explicit persistence policies.
- Ollama: a separately scheduled optional workload/profile, never an implicit dependency of the
  base Noesis deployment.
- Configuration: non-secret `ConfigMap` values plus secret-provider references; no credentials in
  images or manifests.

This is architecture guidance, not evidence of a functioning deployment. Publication, registry
authentication, environment manifests, rollout automation, and rollback automation remain
deliberately deferred.
