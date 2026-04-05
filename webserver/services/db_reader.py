# coding=utf-8
"""
SQLite 数据库异步读取服务
只读操作，不执行任何写入
"""
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite


def get_news_db_path(data_dir: str, target_date: date) -> str:
    """获取新闻数据库路径"""
    return os.path.join(data_dir, "news", f"{target_date}.db")


def get_rss_db_path(data_dir: str, target_date: date) -> str:
    """获取 RSS 数据库路径"""
    return os.path.join(data_dir, "rss", f"{target_date}.db")


def get_available_dates(data_dir: str, db_type: str = "news") -> List[str]:
    """获取有数据的日期列表"""
    db_dir = os.path.join(data_dir, db_type)
    if not os.path.exists(db_dir):
        return []
    
    dates = []
    for f in os.listdir(db_dir):
        if f.endswith(".db") and len(f) == 14:  # YYYY-MM-DD.db
            dates.append(f[:-3])  # 去掉 .db
    
    return sorted(dates, reverse=True)


class NewsDBReader:
    """新闻数据库读取器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def get_connection(self):
        """获取数据库连接"""
        if not os.path.exists(self.db_path):
            return None
        return await aiosqlite.connect(self.db_path)
    
    async def get_today_stats(self) -> Dict[str, Any]:
        """获取今日统计"""
        conn = await self.get_connection()
        if not conn:
            return {"count": 0, "last_crawl": None}
        
        try:
            # 今日条数
            async with conn.execute("SELECT COUNT(*) FROM news_items") as cursor:
                count = (await cursor.fetchone())[0]
            
            # 最近采集时间
            async with conn.execute(
                "SELECT crawl_time FROM crawl_records ORDER BY crawl_time DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                last_crawl = row[0] if row else None
            
            return {"count": count, "last_crawl": last_crawl}
        finally:
            await conn.close()
    
    async def get_platforms_status(self) -> List[Dict[str, Any]]:
        """获取所有平台状态"""
        conn = await self.get_connection()
        if not conn:
            return []
        
        try:
            # 获取最新采集批次
            async with conn.execute(
                "SELECT id, crawl_time FROM crawl_records ORDER BY crawl_time DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    # 没有采集记录，返回所有平台（无状态）
                    async with conn.execute(
                        "SELECT id, name FROM platforms"
                    ) as cursor2:
                        rows = await cursor2.fetchall()
                        return [
                            {"id": r[0], "name": r[1], "status": None, "crawl_time": None}
                            for r in rows
                        ]
                
                crawl_record_id, crawl_time = row
            
            # 获取各平台状态
            async with conn.execute(
                """
                SELECT p.id, p.name, cs.status
                FROM platforms p
                LEFT JOIN crawl_source_status cs ON p.id = cs.platform_id
                WHERE cs.crawl_record_id = ?
                """,
                (crawl_record_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {"id": r[0], "name": r[1], "status": r[2], "crawl_time": crawl_time}
                    for r in rows
                ]
        finally:
            await conn.close()
    
    async def get_top_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取今日热榜 Top N"""
        conn = await self.get_connection()
        if not conn:
            return []
        
        try:
            async with conn.execute(
                """
                SELECT ni.id, ni.title, ni.url, ni.rank, p.name as platform_name
                FROM news_items ni
                JOIN platforms p ON ni.platform_id = p.id
                ORDER BY ni.rank ASC, ni.crawl_count DESC
                LIMIT ?
                """,
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "title": r[1],
                        "url": r[2],
                        "rank": r[3],
                        "platform": r[4]
                    }
                    for r in rows
                ]
        finally:
            await conn.close()
    
    async def get_news_list(
        self,
        platform: Optional[str] = None,
        keyword: Optional[str] = None,
        sort_by: str = "rank",
        page: int = 1,
        per_page: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取新闻列表（分页）
        返回: (数据列表, 总条数)
        """
        conn = await self.get_connection()
        if not conn:
            return [], 0
        
        try:
            # 构建 WHERE 条件
            conditions = []
            params = []
            
            if platform:
                conditions.append("ni.platform_id = ?")
                params.append(platform)
            
            if keyword:
                conditions.append("ni.title LIKE ?")
                params.append(f"%{keyword}%")
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            # 获取总数
            count_sql = f"""
                SELECT COUNT(*)
                FROM news_items ni
                {where_clause}
            """
            async with conn.execute(count_sql, params) as cursor:
                total = (await cursor.fetchone())[0]
            
            # 获取数据
            # 排序字段白名单
            valid_sort_fields = {"rank", "crawl_count", "first_crawl_time", "last_crawl_time"}
            if sort_by not in valid_sort_fields:
                sort_by = "rank"
            
            data_sql = f"""
                SELECT 
                    ni.id, ni.title, ni.url, ni.rank,
                    ni.first_crawl_time, ni.last_crawl_time, ni.crawl_count,
                    p.name as platform_name
                FROM news_items ni
                JOIN platforms p ON ni.platform_id = p.id
                {where_clause}
                ORDER BY ni.{sort_by} ASC
                LIMIT ? OFFSET ?
            """
            query_params = params + [per_page, (page - 1) * per_page]
            
            async with conn.execute(data_sql, query_params) as cursor:
                rows = await cursor.fetchall()
                data = [
                    {
                        "id": r[0],
                        "title": r[1],
                        "url": r[2],
                        "rank": r[3],
                        "first_crawl_time": r[4],
                        "last_crawl_time": r[5],
                        "crawl_count": r[6],
                        "platform": r[7]
                    }
                    for r in rows
                ]
            
            return data, total
        finally:
            await conn.close()
    
    async def get_rank_history(self, news_item_id: int) -> List[Dict[str, Any]]:
        """获取新闻排名历史"""
        conn = await self.get_connection()
        if not conn:
            return []
        
        try:
            async with conn.execute(
                """
                SELECT rank, crawl_time
                FROM rank_history
                WHERE news_item_id = ?
                ORDER BY crawl_time ASC
                """,
                (news_item_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {"rank": r[0], "crawl_time": r[1]}
                    for r in rows
                ]
        finally:
            await conn.close()
    
    async def get_platforms(self) -> List[Dict[str, Any]]:
        """获取所有平台"""
        conn = await self.get_connection()
        if not conn:
            return []
        
        try:
            async with conn.execute(
                "SELECT id, name FROM platforms ORDER BY name"
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"id": r[0], "name": r[1]} for r in rows]
        finally:
            await conn.close()
    
    async def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取近 N 天采集统计"""
        conn = await self.get_connection()
        if not conn:
            return []
        
        try:
            async with conn.execute(
                """
                SELECT 
                    DATE(crawl_time) as date,
                    COUNT(*) as count
                FROM crawl_records
                WHERE crawl_time >= date('now', '-{} days')
                GROUP BY DATE(crawl_time)
                ORDER BY date ASC
                """.format(days)
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"date": r[0], "count": r[1]} for r in rows]
        finally:
            await conn.close()


class RSSDBReader:
    """RSS 数据库读取器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def get_connection(self):
        """获取数据库连接"""
        if not os.path.exists(self.db_path):
            return None
        return await aiosqlite.connect(self.db_path)
    
    async def get_today_stats(self) -> Dict[str, Any]:
        """获取今日统计"""
        conn = await self.get_connection()
        if not conn:
            return {"count": 0, "last_crawl": None}
        
        try:
            async with conn.execute("SELECT COUNT(*) FROM rss_items") as cursor:
                count = (await cursor.fetchone())[0]
            
            async with conn.execute(
                "SELECT crawl_time FROM rss_crawl_records ORDER BY crawl_time DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                last_crawl = row[0] if row else None
            
            return {"count": count, "last_crawl": last_crawl}
        finally:
            await conn.close()
    
    async def get_feeds_status(self) -> List[Dict[str, Any]]:
        """获取 RSS 源状态"""
        conn = await self.get_connection()
        if not conn:
            return []
        
        try:
            async with conn.execute(
                """
                SELECT 
                    id, name, feed_url, last_fetch_time, 
                    last_fetch_status, item_count
                FROM rss_feeds
                ORDER BY name
                """
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "name": r[1],
                        "url": r[2],
                        "last_fetch": r[3],
                        "status": r[4],
                        "count": r[5]
                    }
                    for r in rows
                ]
        finally:
            await conn.close()
    
    async def get_items(
        self,
        feed_id: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        per_page: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取 RSS 文章列表"""
        conn = await self.get_connection()
        if not conn:
            return [], 0
        
        try:
            conditions = []
            params = []
            
            if feed_id:
                conditions.append("ri.feed_id = ?")
                params.append(feed_id)
            
            if keyword:
                conditions.append("(ri.title LIKE ? OR ri.summary LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            # 总数
            count_sql = f"""
                SELECT COUNT(*)
                FROM rss_items ri
                {where_clause}
            """
            async with conn.execute(count_sql, params) as cursor:
                total = (await cursor.fetchone())[0]
            
            # 数据
            data_sql = f"""
                SELECT 
                    ri.id, ri.title, ri.url, ri.published_at,
                    ri.summary, ri.author, rf.name as feed_name
                FROM rss_items ri
                JOIN rss_feeds rf ON ri.feed_id = rf.id
                {where_clause}
                ORDER BY ri.published_at DESC
                LIMIT ? OFFSET ?
            """
            query_params = params + [per_page, (page - 1) * per_page]
            
            async with conn.execute(data_sql, query_params) as cursor:
                rows = await cursor.fetchall()
                data = [
                    {
                        "id": r[0],
                        "title": r[1],
                        "url": r[2],
                        "published_at": r[3],
                        "summary": r[4],
                        "author": r[5],
                        "feed": r[6]
                    }
                    for r in rows
                ]
            
            return data, total
        finally:
            await conn.close()
    
    async def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取近 N 天 RSS 采集统计"""
        conn = await self.get_connection()
        if not conn:
            return []
        
        try:
            async with conn.execute(
                """
                SELECT 
                    DATE(crawl_time) as date,
                    COUNT(*) as count
                FROM rss_crawl_records
                WHERE crawl_time >= date('now', '-{} days')
                GROUP BY DATE(crawl_time)
                ORDER BY date ASC
                """.format(days)
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"date": r[0], "count": r[1]} for r in rows]
        finally:
            await conn.close()


class ScheduleDBReader:
    """调度执行记录读取器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def get_connection(self):
        if not os.path.exists(self.db_path):
            return None
        return await aiosqlite.connect(self.db_path)
    
    async def get_today_executions(self, today: str) -> List[Dict[str, Any]]:
        """获取今日执行记录"""
        conn = await self.get_connection()
        if not conn:
            return []
        
        try:
            async with conn.execute(
                """
                SELECT executed_at, period_key, action
                FROM period_executions
                WHERE execution_date = ?
                ORDER BY executed_at DESC
                """,
                (today,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "executed_at": r[0],
                        "period_key": r[1],
                        "action": r[2]
                    }
                    for r in rows
                ]
        finally:
            await conn.close()
