"""Synthetic fixtures for DMS pages (structure verified live 2026-10-13)."""

from __future__ import annotations

ROW_TEMPLATE = """
<tr class=" {status_class}selectableRow">
  <td class="dT-details-toggler"></td>
  <td><label class="checkbox m-n i-checks">
    <input name="name" aria-label="Auswahl-Checkbox"
           class="singleCheckbox multiSelectTableCheckbox"
           value="{doc_id}" type="checkbox"></label></td>
  <td><label class="label bg-light lter text-muted text-xs m-l-xs">{status}</label></td>
  <td style="max-width:300px;" title="{name}">
    <div class="filename_with_marker">
      <a href="/dms/document/show/{doc_id}" class="split_truncate link documentname">
        <span class="truncate">{stem}</span><span class="truncate truncate-extension">{ext}</span>
      </a></div></td>
  <td>{size}</td>
  <td>{released}</td>
  <td>{downloaded}</td>
  <td>{category}</td>
  <td class="text-right"><div class="btn-group btn-icon-width-2x">
    <a href="/dms/document/show/{doc_id}" class="btn btn-primary btn-sm"></a>
    <a href="/dms/document/download/{doc_id}" class="btn btn-primary btn-sm" target="_blank"></a>
  </div></td>
</tr>
"""


def make_row(
    doc_id: str,
    name: str,
    status: str = "gelesen",
    size: str = "140 KB",
    released: str = "09.10.2026, 11:56:35",
    downloaded: str = "",
    category: str = "Belegprüfung",
) -> str:
    stem, _, ext = name.rpartition(".")
    if not _:
        stem, ext = name, ""
    return ROW_TEMPLATE.format(
        doc_id=doc_id,
        name=name,
        status=status,
        status_class="new " if status == "neu" else "",
        size=size,
        released=released,
        downloaded=downloaded,
        category=category,
        stem=stem,
        ext=("." + ext) if ext else "",
    )


CATEGORY_SCRIPTS = """
<script>currentCategory = new DmsCategory()
    .setId(1) .setName('Belegprüfung') .setCount(1);</script>
<script>currentCategory = new DmsCategory()
    .setId(2) .setName('Allgemein') .setCount(1);
    currentCategory.addChild(new DmsCategory()
    .setId(3) .setName('Unterordner') .setCount(0));</script>
"""


def make_document_page(
    rows: list[str],
    total: int,
    page_count: int = 1,
    with_categories: bool = True,
) -> str:
    return f"""
<html><body>
{CATEGORY_SCRIPTS if with_categories else ""}
<table id="selectTable"><tbody>
{''.join(rows)}
</tbody></table>
<div class="paginator">
  <ul class="pagination pagination-mini customized pagination-colored"
      title="1 - {total} / {total} / {page_count}">
    <li class="active"><a class="forceLoading" href="/dms/document/list/-1?page=1">1</a></li>
  </ul>
</div>
</body></html>
"""


OBJECT_PAGE = """
<html><body>
<aside class="aside-lg bg-middle hide" id="objects">
  <div class="auto wrapper" id="objectSearchTarget">
    <a href="/application/essential/switch-object/652/L3BvcnRhbC9vYmplY3Qvc2hvdw=="
       class="list-group-item active">
      <span class="custom icon-selected-object icon-md"></span>
      Musterstr. 1    <br/>
      <span class="text-xs">Musterstr. 1, Musterstadt</span>
    </a>
    <a href="/application/essential/switch-object/653/L3BvcnRhbC9vYmplY3Qvc2hvdw=="
       class="list-group-item">
      <span class="custom icon-selected-object icon-md"></span>
      Beispielweg 2    <br/>
      <span class="text-xs">Beispielweg 2, Beispielstadt</span>
    </a>
  </div>
</aside>
<aside class="aside-lg bg-middle hide" id="contracts">
  <div class="auto wrapper" id="rucrSearchTarget">
    <a href="/application/essential/switch-rent-unit-contact-relation/3071/L3BvcnRhbA=="
       class="list-group-item active">
      <span class="custom icon-administrative-unit icon-md"></span> WHG 1 <br />
      <span class="text-xs font-bold">Wohnung, seit 01.01.2010</span>
    </a>
  </div>
</aside>
</body></html>
"""

TICKET_PAGE = """
<html><body>
<table><tbody>
<tr data-id="136">
  <td>TSP#136</td>
  <td><a href="/communicator/ticket/show/136" class="split_truncate link">Wasser undicht</a></td>
  <td><span class="txt-sm underlined">Vorgang</span></td>
  <td>in Bearbeitung</td>
  <td><span title="Musterstr. 1, 12345 Musterstadt"></span></td>
  <td>03.02.2026, 12:40:24</td>
  <td>01.02.2026, 08:00:00</td>
  <td>2</td>
  <td>1</td>
  <td><a href="/communicator/ticket/show/136" class="btn btn-primary btn-sm"></a></td>
</tr>
</tbody></table>
</body></html>
"""
