# MiroFish (fork Loulen)

Fork de `666ghj/MiroFish` pour corrections et adaptations Ippon.

## Upstream

- **Repo** : `github.com/666ghj/MiroFish`
- **Licence** : AGPL-3.0
- **Remote** : `upstream` pointe vers l'original, `origin` vers `Loulen/MiroFish`

## Modifications par rapport à upstream

### fix: ne pas relancer la simulation en naviguant sur /start

**Fichier** : `frontend/src/components/Step3Simulation.vue`

Le `onMounted` du composant Step3 appelait `doStartSimulation()` avec `force: true` inconditionnellement. Naviguer vers `/simulation/:id/start` tuait toute simulation en cours et relancait depuis le round 0.

Le fix vérifie `getRunStatus()` d'abord :
- `running`/`starting` : reprend le polling sans relancer
- `completed`/`stopped` : affiche les résultats
- `failed` : affiche l'erreur, laisse l'utilisateur décider de relancer
- Aucun état : lance la simulation comme avant

### feat: localisation française (UI + prompts LLM)

**Fichiers modifiés** :
- `locales/fr.json` — traduction complète des 629 clés UI
- `frontend/src/i18n/index.js` — locale par défaut `fr`, fallback `en`
- `backend/app/utils/locale.py` — fallback `fr` côté serveur
- `backend/app/services/report_agent.py` — tous les prompts LLM traduits en français
- `backend/app/services/ontology_generator.py` — prompt système traduit
- `backend/app/services/simulation_config_generator.py` — prompts de config traduits
- `backend/app/services/oasis_profile_generator.py` — prompts de génération de persona traduits
- `backend/app/services/zep_tools.py` — prompts d'interview/recherche traduits
- `frontend/src/views/Process.vue` — alert hardcodé chinois remplacé

## Stack

- **Frontend** : Vue 3 + Vite (dev server en dev, pas de build prod dans l'image officielle)
- **Backend** : Flask (port 5001)
- **LLM** : OpenAI-compatible (OpenRouter dans notre cas)
- **Simulation** : CAMEL-OASIS (Twitter + Reddit parallèles)
- **i18n** : FR par défaut (fallback EN), ZH disponible

## Bugs connus upstream

- Le `run-status` API mélange les metadata (total_rounds, PID) entre runs successifs quand on relance avec `force: true` et un `max_rounds` différent
- Le frontend tourne en mode dev (Vite dev server) y compris en production dans l'image Docker officielle
- Pas de mécanisme de reprise : si la page `/start` est ouverte, elle relance toujours (corrigé dans ce fork)

## Déploiement sur le VPS

L'instance `mirofish-1ijl` utilise encore l'image officielle `ghcr.io/666ghj/MiroFish:latest`. Le patch est appliqué en hotfix dans le container via HMR Vite (non persisté au restart). Pour persister, il faudra builder depuis ce fork :

```bash
# Depuis le VPS
cd /docker/mirofish-1ijl
# Remplacer l'image dans docker-compose.yml par un build depuis le fork
# ou appliquer le patch au démarrage
```
