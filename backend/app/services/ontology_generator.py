"""
本体生成服务
接口1：分析文本内容，生成适合社会模拟的实体和关系类型定义
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction

logger = logging.getLogger(__name__)


def _to_pascal_case(name: str) -> str:
    """将任意格式的名称转换为 PascalCase（如 'works_for' -> 'WorksFor', 'person' -> 'Person'）"""
    # 按非字母数字字符分割
    parts = re.split(r'[^a-zA-Z0-9]+', name)
    # 再按 camelCase 边界分割（如 'camelCase' -> ['camel', 'Case']）
    words = []
    for part in parts:
        words.extend(re.sub(r'([a-z])([A-Z])', r'\1_\2', part).split('_'))
    # 每个词首字母大写，过滤空串
    result = ''.join(word.capitalize() for word in words if word)
    return result if result else 'Unknown'


# 本体生成的系统提示词
ONTOLOGY_SYSTEM_PROMPT = """Tu es un expert professionnel en conception d'ontologies de graphes de connaissances. Ta tâche est d'analyser le contenu textuel et les besoins de simulation donnés, et de concevoir des types d'entités et de relations adaptés à la **simulation d'opinion publique sur les réseaux sociaux**.

**Important : tu dois produire des données au format JSON valide, sans aucun autre contenu.**

## Contexte de la mission principale

Nous construisons un **système de simulation d'opinion publique sur les réseaux sociaux**. Dans ce système :
- Chaque entité est un « compte » ou « acteur » capable de s'exprimer, d'interagir et de diffuser de l'information sur les réseaux sociaux
- Les entités s'influencent mutuellement, retransmettent, commentent et répondent
- Nous devons simuler les réactions des différentes parties dans un événement d'opinion publique et les chemins de propagation de l'information

Par conséquent, **les entités doivent être des acteurs réels existant dans la réalité, capables de s'exprimer et d'interagir sur les réseaux sociaux** :

**Peuvent être** :
- Des individus concrets (personnalités publiques, parties prenantes, leaders d'opinion, experts, personnes ordinaires)
- Des entreprises (y compris leurs comptes officiels)
- Des organisations (universités, associations, ONG, syndicats, etc.)
- Des administrations, organismes de régulation
- Des médias (journaux, chaînes TV, médias indépendants, sites web)
- Des plateformes de réseaux sociaux elles-mêmes
- Des représentants de groupes spécifiques (associations d'anciens élèves, groupes de fans, groupes de défense de droits, etc.)

**Ne peuvent pas être** :
- Des concepts abstraits (comme « opinion publique », « émotion », « tendance »)
- Des thèmes/sujets (comme « intégrité académique », « réforme de l'éducation »)
- Des opinions/attitudes (comme « camp favorable », « camp opposé »)

## Format de sortie

Produire au format JSON, avec la structure suivante :

```json
{
    "entity_types": [
        {
            "name": "Nom du type d'entité (anglais, PascalCase)",
            "description": "Description courte (anglais, max 100 caractères)",
            "attributes": [
                {
                    "name": "Nom de l'attribut (anglais, snake_case)",
                    "type": "text",
                    "description": "Description de l'attribut"
                }
            ],
            "examples": ["Exemple d'entité 1", "Exemple d'entité 2"]
        }
    ],
    "edge_types": [
        {
            "name": "Nom du type de relation (anglais, UPPER_SNAKE_CASE)",
            "description": "Description courte (anglais, max 100 caractères)",
            "source_targets": [
                {"source": "Type d'entité source", "target": "Type d'entité cible"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "Brève analyse du contenu textuel"
}
```

## Guide de conception (extrêmement important !)

### 1. Conception des types d'entités - À respecter strictement

**Exigence de quantité : exactement 10 types d'entités**

**Exigence de structure hiérarchique (doit inclure à la fois des types spécifiques et des types par défaut)** :

Vos 10 types d'entités doivent inclure les niveaux suivants :

A. **Types par défaut (obligatoires, placés en dernière position de la liste)** :
   - `Person` : Type par défaut pour tout individu personne physique. Quand une personne n'appartient à aucun type de personne plus spécifique, elle est classée ici.
   - `Organization` : Type par défaut pour toute organisation. Quand une organisation n'appartient à aucun type d'organisation plus spécifique, elle est classée ici.

B. **Types spécifiques (8, conçus selon le contenu du texte)** :
   - Concevoir des types plus spécifiques pour les rôles principaux apparaissant dans le texte
   - Par exemple : si le texte concerne un événement académique, on peut avoir `Student`, `Professor`, `University`
   - Par exemple : si le texte concerne un événement commercial, on peut avoir `Company`, `CEO`, `Employee`

**Pourquoi des types par défaut sont nécessaires** :
- Le texte fait apparaître divers personnages, comme des « enseignants », des « passants », des « internautes »
- S'il n'y a pas de type spécifique correspondant, ils doivent être classés dans `Person`
- De même, les petites organisations, groupes temporaires, etc. doivent être classés dans `Organization`

**Principes de conception des types spécifiques** :
- Identifier les types de rôles fréquents ou clés dans le texte
- Chaque type spécifique doit avoir des limites claires, éviter les chevauchements
- La description doit clairement expliquer la différence entre ce type et le type par défaut

### 2. Conception des types de relations

- Quantité : 6-10
- Les relations doivent refléter les liens réels dans les interactions sur les réseaux sociaux
- S'assurer que les source_targets des relations couvrent les types d'entités que vous avez définis

### 3. Conception des attributs

- 1 à 3 attributs clés par type d'entité
- **Attention** : les noms d'attributs ne peuvent pas utiliser `name`, `uuid`, `group_id`, `created_at`, `summary` (ce sont des mots réservés du système)
- Recommandés : `full_name`, `title`, `role`, `position`, `location`, `description`, etc.

## Référence des types d'entités

**Catégorie individus (spécifiques)** :
- Student : Étudiant
- Professor : Professeur/Chercheur
- Journalist : Journaliste
- Celebrity : Célébrité/Influenceur
- Executive : Cadre dirigeant
- Official : Fonctionnaire gouvernemental
- Lawyer : Avocat
- Doctor : Médecin

**Catégorie individus (par défaut)** :
- Person : Toute personne physique (utilisé quand aucun type spécifique ne correspond)

**Catégorie organisations (spécifiques)** :
- University : Établissement d'enseignement supérieur
- Company : Entreprise
- GovernmentAgency : Administration publique
- MediaOutlet : Média
- Hospital : Hôpital
- School : Établissement scolaire
- NGO : Organisation non gouvernementale

**Catégorie organisations (par défaut)** :
- Organization : Toute organisation (utilisé quand aucun type spécifique ne correspond)

## Référence des types de relations

- WORKS_FOR : Travaille pour
- STUDIES_AT : Étudie à
- AFFILIATED_WITH : Affilié à
- REPRESENTS : Représente
- REGULATES : Régule
- REPORTS_ON : Rapporte sur
- COMMENTS_ON : Commente
- RESPONDS_TO : Répond à
- SUPPORTS : Soutient
- OPPOSES : S'oppose à
- COLLABORATES_WITH : Collabore avec
- COMPETES_WITH : En concurrence avec
"""


class OntologyGenerator:
    """
    本体生成器
    分析文本内容，生成实体和关系类型定义
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成本体定义
        
        Args:
            document_texts: 文档文本列表
            simulation_requirement: 模拟需求描述
            additional_context: 额外上下文
            
        Returns:
            本体定义（entity_types, edge_types等）
        """
        # 构建用户消息
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        lang_instruction = get_language_instruction()
        system_prompt = f"{ONTOLOGY_SYSTEM_PROMPT}\n\n{lang_instruction}\nIMPORTANT: Entity type names MUST be in English PascalCase (e.g., 'PersonEntity', 'MediaOrganization'). Relationship type names MUST be in English UPPER_SNAKE_CASE (e.g., 'WORKS_FOR'). Attribute names MUST be in English snake_case. Only description fields and analysis_summary should use the specified language above."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # 调用LLM
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        # 验证和后处理
        result = self._validate_and_process(result)
        
        return result
    
    # 传给 LLM 的文本最大长度（5万字）
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """构建用户消息"""
        
        # 合并文本
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # 如果文本超过5万字，截断（仅影响传给LLM的内容，不影响图谱构建）
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(texte original de {original_length} caractères, les {self.MAX_TEXT_LENGTH_FOR_LLM} premiers ont été extraits pour l'analyse ontologique)..."
        
        message = f"""## Besoin de simulation

{simulation_requirement}

## Contenu du document

{combined_text}
"""

        if additional_context:
            message += f"""
## Informations complémentaires

{additional_context}
"""

        message += """
Sur la base du contenu ci-dessus, concevez des types d'entités et de relations adaptés à la simulation d'opinion publique.

**Règles obligatoires** :
1. Produire exactement 10 types d'entités
2. Les 2 derniers doivent être les types par défaut : Person (par défaut pour les individus) et Organization (par défaut pour les organisations)
3. Les 8 premiers sont des types spécifiques conçus selon le contenu du texte
4. Tous les types d'entités doivent être des acteurs réels pouvant s'exprimer, pas des concepts abstraits
5. Les noms d'attributs ne peuvent pas utiliser name, uuid, group_id et autres mots réservés, utiliser full_name, org_name, etc. à la place
"""
        
        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证和后处理结果"""
        
        # 确保必要字段存在
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""
        
        # 验证实体类型
        # 记录原始名称到 PascalCase 的映射，用于后续修正 edge 的 source_targets 引用
        entity_name_map = {}
        for entity in result["entity_types"]:
            # 强制将 entity name 转为 PascalCase（Zep API 要求）
            if "name" in entity:
                original_name = entity["name"]
                entity["name"] = _to_pascal_case(original_name)
                if entity["name"] != original_name:
                    logger.warning(f"Entity type name '{original_name}' auto-converted to '{entity['name']}'")
                entity_name_map[original_name] = entity["name"]
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # 确保description不超过100字符
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # 验证关系类型
        for edge in result["edge_types"]:
            # 强制将 edge name 转为 SCREAMING_SNAKE_CASE（Zep API 要求）
            if "name" in edge:
                original_name = edge["name"]
                edge["name"] = original_name.upper()
                if edge["name"] != original_name:
                    logger.warning(f"Edge type name '{original_name}' auto-converted to '{edge['name']}'")
            # 修正 source_targets 中的实体名称引用，与转换后的 PascalCase 保持一致
            for st in edge.get("source_targets", []):
                if st.get("source") in entity_name_map:
                    st["source"] = entity_name_map[st["source"]]
                if st.get("target") in entity_name_map:
                    st["target"] = entity_name_map[st["target"]]
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        # Zep API 限制：最多 10 个自定义实体类型，最多 10 个自定义边类型
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # 去重：按 name 去重，保留首次出现的
        seen_names = set()
        deduped = []
        for entity in result["entity_types"]:
            name = entity.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                deduped.append(entity)
            elif name in seen_names:
                logger.warning(f"Duplicate entity type '{name}' removed during validation")
        result["entity_types"] = deduped

        # 兜底类型定义
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        # 检查是否已有兜底类型
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # 需要添加的兜底类型
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # 如果添加后会超过 10 个，需要移除一些现有类型
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # 计算需要移除多少个
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # 从末尾移除（保留前面更重要的具体类型）
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # 添加兜底类型
            result["entity_types"].extend(fallbacks_to_add)
        
        # 最终确保不超过限制（防御性编程）
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        将本体定义转换为Python代码（类似ontology.py）
        
        Args:
            ontology: 本体定义
            
        Returns:
            Python代码字符串
        """
        code_lines = [
            '"""',
            'Définitions des types d\'entités personnalisés',
            'Généré automatiquement par MiroFish pour la simulation d\'opinions',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== Définitions des types d\'entités ==============',
            '',
        ]
        
        # 生成实体类型
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== Définitions des types de relations ==============')
        code_lines.append('')
        
        # 生成关系类型
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # 转换为PascalCase类名
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # 生成类型字典
        code_lines.append('# ============== Configuration des types ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # 生成边的source_targets映射
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)

