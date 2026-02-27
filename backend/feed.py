import datetime

def generate_atom_feed(articles):
    feed = '<?xml version="1.0" encoding="utf-8"?>\n'
    feed += '<feed xmlns="http://www.w3.org/2005/Atom">\n'
    feed += '  <title>AI Knowledge Hub Public Feed</title>\n'
    feed += '  <link href="http://localhost:8000/feed/public" rel="self"/>\n'
    feed += f'  <updated>{datetime.datetime.now(datetime.timezone.utc).isoformat()}</updated>\n'
    feed += '  <id>http://localhost:8000/feed/public</id>\n'
    
    for article in articles:
        feed += '  <entry>\n'
        feed += f'    <title>{article.title}</title>\n'
        feed += f'    <link href="{article.url}"/>\n'
        feed += f'    <id>{article.url}</id>\n'
        updated_time = article.published_at.isoformat() if article.published_at else datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not updated_time.endswith('Z') and '+' not in updated_time:
             updated_time += 'Z'
        feed += f'    <updated>{updated_time}</updated>\n'
        feed += f'    <summary>{article.summary_ja or article.summary or ""}</summary>\n'
        content = f"Score: {article.score}<br/>Business Point: {article.business_point}<br/>Tags: {','.join(article.tags or [])}"
        feed += f'    <content type="html"><![CDATA[{content}]]></content>\n'
        feed += '  </entry>\n'
        
    feed += '</feed>'
    return feed
