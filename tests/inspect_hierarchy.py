# inspect_hierarchy.py —— 查看父子结构与元数据（不加载 embedding 模型）
from collections import Counter

import chromadb
from llama_index.core import StorageContext
from llama_index.core.schema import NodeRelationship
from llama_index.vector_stores.chroma import ChromaVectorStore

from backend.rag.knowledge import (
    CHROMA_DIR,          # Chroma 持久化目录
    COLLECTION_NAME,     # Chroma 集合名
    STORAGE_DIR,         # docstore/indexstore 持久化目录
)

LIMIT = 30               # 最多打印多少个节点，避免刷屏


def _count(rel):
    """统计关系数量：可能是单个对象，也可能是列表"""
    if not rel:
        return 0
    if isinstance(rel, list):
        return len(rel)
    return 1


def _level_of(node) -> str:
    """根据父子关系判断节点层级"""
    children = _count(node.relationships.get(NodeRelationship.CHILD, []))
    parent = _count(node.relationships.get(NodeRelationship.PARENT, []))
    if parent == 0 and children > 0:
        return "根节点"
    if parent > 0 and children > 0:
        return "中间节点"
    if parent > 0 and children == 0:
        return "叶子节点"
    return "单层节点"


def main():
    # 1. 连接本地 Chroma 持久化目录（不会启动服务）
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # 2. 拿到知识库集合；没有就提示先建索引
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception:
        print("未找到 Chroma 集合，请先运行：python -m tests.rag_smoke")
        return

    # 3. 用集合构造 LlamaIndex 的向量存储适配器
    vector_store = ChromaVectorStore(chroma_collection=collection)

    # 4. 加载 docstore（父块/中块/子块都在里面），并挂上向量存储
    try:
        storage_context = StorageContext.from_defaults(
            persist_dir=STORAGE_DIR,
            vector_store=vector_store,
        )
    except Exception as e:
        print("加载 storage 失败：", e)
        print("请确认 storage/docstore.json 存在，必要时重建索引。")
        return

    # 5. 取出所有节点
    nodes = list(storage_context.docstore.docs.values())

    # 6. 打印总体统计
    print("Chroma 目录：", CHROMA_DIR)
    print("Chroma 向量数：", collection.count())
    print("docstore 节点总数：", len(nodes))
    print("-" * 80)

    # 7. 排序：按文件名、再按内容长度，便于阅读
    nodes.sort(key=lambda n: (
        n.metadata.get("file_name", ""),
        len(n.get_content()),
    ))

    # 8. 逐个打印节点
    for node in nodes[:LIMIT]:
        meta = node.metadata or {}
        print(
            node.node_id[:8],
            "|", _level_of(node),
            "| 文件:", meta.get("file_name", "未知"),
            "| 部门:", meta.get("department", "未标注"),
            "| 密级:", meta.get("security_level", "未标注"),
            "| 状态:", meta.get("doc_status", "未标注"),
            "| 页码:", meta.get("page_label", meta.get("page", "—")),
            "| 字数:", len(node.get_content()),
        )

    if len(nodes) > LIMIT:
        print(f"... 其余 {len(nodes) - LIMIT} 个节点未打印")

    # 9. 汇总统计
    print("-" * 80)
    file_counter = Counter(
        (n.metadata or {}).get("file_name", "未知") for n in nodes)
    level_counter = Counter(_level_of(n) for n in nodes)
    print("按文件统计：", file_counter)
    print("按层级统计：", level_counter)


if __name__ == "__main__":
    main()