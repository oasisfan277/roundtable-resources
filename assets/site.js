(() => {
  const skipLinks = Array.from(document.querySelectorAll(".skip-link"));
  const focusLinks = Array.from(document.querySelectorAll(".skip-link, .back-to-top a"));
  const themeChoices = Array.from(document.querySelectorAll("[data-theme-choice]"));
  const comfortChoices = Array.from(document.querySelectorAll("[data-comfort-choice]"));
  const search = document.querySelector("#resource-search");
  const clearButton = document.querySelector("#clear-search");
  const searchAll = document.querySelector("#search-all");
  const filterBoxes = Array.from(document.querySelectorAll("[data-search-filter]"));
  const resultsSection = document.querySelector("#search-results-section");
  const resultsHeading = document.querySelector("#search-results-heading");
  const status = document.querySelector("#result-count");
  const noResults = document.querySelector("#no-results");
  const resultsList = document.querySelector("#search-results");
  const resources = Array.isArray(window.ROUND_TABLE_RESOURCES) ? window.ROUND_TABLE_RESOURCES : [];
  const pageSizeOptions = [25, 50, 75, 100];
  const pageSizeStorageKey = "roundtable-resources-page-size";
  let paginationControlId = 0;

  function savedTheme() {
    try {
      return localStorage.getItem("roundtable-theme");
    } catch (error) {
      return null;
    }
  }

  function saveTheme(theme) {
    try {
      if (theme === "dark" || theme === "light-contrast") {
        localStorage.setItem("roundtable-theme", theme);
      } else {
        localStorage.removeItem("roundtable-theme");
      }
    } catch (error) {}
  }

  function savedComfort() {
    try {
      return localStorage.getItem("roundtable-comfort");
    } catch (error) {
      return null;
    }
  }

  function saveComfort(value) {
    try {
      if (value === "large" || value === "xlarge") {
        localStorage.setItem("roundtable-comfort", value);
      } else {
        localStorage.removeItem("roundtable-comfort");
      }
    } catch (error) {}
  }

  function applyTheme(theme, persist = false) {
    const selectedTheme = theme === "dark" || theme === "light-contrast" ? theme : "standard";
    if (selectedTheme === "standard") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", selectedTheme);
    }
    themeChoices.forEach((choice) => {
      choice.checked = choice.value === selectedTheme;
    });
    if (persist) {
      saveTheme(selectedTheme);
    }
  }

  function applyComfort(value, persist = false) {
    const selectedComfort = value === "large" || value === "xlarge" ? value : "normal";
    if (selectedComfort === "normal") {
      document.documentElement.removeAttribute("data-comfort");
    } else {
      document.documentElement.setAttribute("data-comfort", selectedComfort);
    }
    comfortChoices.forEach((choice) => {
      choice.checked = choice.value === selectedComfort;
    });
    if (persist) {
      saveComfort(selectedComfort);
    }
  }

  applyTheme(savedTheme());
  applyComfort(savedComfort());
  themeChoices.forEach((choice) => {
    choice.addEventListener("change", () => {
      if (choice.checked) {
        applyTheme(choice.value, true);
      }
    });
  });
  comfortChoices.forEach((choice) => {
    choice.addEventListener("change", () => {
      if (choice.checked) {
        applyComfort(choice.value, true);
      }
    });
  });

  function isTypingOrControl(target) {
    return Boolean(
      target.closest(
        "input, textarea, select, button, summary, [contenteditable='true'], [role='textbox']"
      )
    );
  }

  function sameOriginReferrer() {
    if (!document.referrer) return "";
    try {
      const referrer = new URL(document.referrer);
      if (referrer.origin === window.location.origin && referrer.href !== window.location.href) {
        return referrer.href;
      }
    } catch (error) {}
    return "";
  }

  document.addEventListener("keydown", (event) => {
    if (
      event.key !== "ArrowLeft" ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.shiftKey ||
      event.repeat ||
      isTypingOrControl(event.target)
    ) {
      return;
    }

    const referrer = sameOriginReferrer();
    if (window.history.length > 1) {
      event.preventDefault();
      window.history.back();
    } else if (referrer) {
      event.preventDefault();
      window.location.href = referrer;
    }
  });

  focusLinks.forEach((focusLink) => {
    focusLink.addEventListener("click", () => {
      const href = focusLink.getAttribute("href") || "";
      if (!href.startsWith("#") || href.length < 2) return;
      const target = document.getElementById(href.slice(1));
      if (!target || typeof target.focus !== "function") return;
      window.setTimeout(() => {
        target.focus({ preventScroll: true });
      }, 0);
    });
  });

  function savedPageSize() {
    try {
      const value = Number.parseInt(localStorage.getItem(pageSizeStorageKey) || "", 10);
      if (pageSizeOptions.includes(value)) {
        return value;
      }
    } catch (error) {}
    return pageSizeOptions[0];
  }

  function savePageSize(value) {
    try {
      localStorage.setItem(pageSizeStorageKey, String(value));
    } catch (error) {}
  }

  function createPaginationControls({ label, pageSizeLabel, itemNamePlural, onPrevious, onNext, onPageSizeChange }) {
    paginationControlId += 1;
    const selectId = `pagination-size-${paginationControlId}`;

    const root = document.createElement("nav");
    root.className = "pagination-controls";
    root.setAttribute("aria-label", `${label} pagination`);
    root.hidden = true;

    const sizeWrapper = document.createElement("div");
    sizeWrapper.className = "pagination-size";

    const selectLabel = document.createElement("label");
    selectLabel.htmlFor = selectId;
    selectLabel.textContent = pageSizeLabel;

    const select = document.createElement("select");
    select.id = selectId;
    pageSizeOptions.forEach((optionValue) => {
      const option = document.createElement("option");
      option.value = String(optionValue);
      option.textContent = `${optionValue} ${itemNamePlural}`;
      select.append(option);
    });
    select.addEventListener("change", () => {
      onPageSizeChange(Number.parseInt(select.value, 10));
    });

    sizeWrapper.append(selectLabel, select);

    const statusText = document.createElement("p");
    statusText.className = "pagination-status";
    statusText.setAttribute("aria-live", "polite");
    statusText.setAttribute("aria-atomic", "true");

    const buttonWrapper = document.createElement("div");
    buttonWrapper.className = "pagination-buttons";

    const previousButton = document.createElement("button");
    previousButton.type = "button";
    previousButton.textContent = "Previous";
    previousButton.setAttribute("aria-label", `Previous page of ${label}`);
    previousButton.addEventListener("click", onPrevious);

    const nextButton = document.createElement("button");
    nextButton.type = "button";
    nextButton.textContent = "Next";
    nextButton.setAttribute("aria-label", `Next page of ${label}`);
    nextButton.addEventListener("click", onNext);

    buttonWrapper.append(previousButton, nextButton);
    root.append(sizeWrapper, statusText, buttonWrapper);
    return { root, select, statusText, previousButton, nextButton };
  }

  function createPager({
    containers,
    label,
    pageSizeLabel,
    itemName,
    itemNamePlural,
    total,
    renderRange,
  }) {
    let currentPage = 1;
    let pageSize = savedPageSize();
    const controls = containers
      .filter(Boolean)
      .map((container) => {
        const control = createPaginationControls({
          label,
          pageSizeLabel,
          itemNamePlural,
          onPrevious: () => {
            currentPage -= 1;
            render();
          },
          onNext: () => {
            currentPage += 1;
            render();
          },
          onPageSizeChange: (value) => {
            if (!pageSizeOptions.includes(value)) return;
            pageSize = value;
            currentPage = 1;
            savePageSize(value);
            render();
          },
        });
        container.replaceChildren(control.root);
        return control;
      });

    function updateControls(totalCount, start, end, pageCount) {
      const showControls = totalCount > pageSizeOptions[0];
      const noun = totalCount === 1 ? itemName : itemNamePlural;
      let statusText = "";
      if (totalCount > 0) {
        statusText =
          totalCount <= pageSize
            ? `Showing all ${totalCount} ${noun}.`
            : `Showing ${start + 1} to ${end} of ${totalCount} ${noun}. Page ${currentPage} of ${pageCount}.`;
      }

      controls.forEach((control) => {
        control.root.hidden = !showControls;
        control.select.value = String(pageSize);
        control.statusText.textContent = statusText;
        control.previousButton.disabled = currentPage <= 1;
        control.nextButton.disabled = currentPage >= pageCount;
      });
    }

    function render() {
      const totalCount = total();
      const pageCount = Math.max(1, Math.ceil(totalCount / pageSize));
      currentPage = Math.min(Math.max(currentPage, 1), pageCount);
      const start = totalCount === 0 ? 0 : (currentPage - 1) * pageSize;
      const end = Math.min(start + pageSize, totalCount);
      renderRange(start, end, totalCount, currentPage, pageCount, pageSize);
      updateControls(totalCount, start, end, pageCount);
    }

    function hide() {
      controls.forEach((control) => {
        control.root.hidden = true;
      });
    }

    return {
      render,
      reset() {
        currentPage = 1;
        render();
      },
      hide,
    };
  }

  function initializeResourcePagination() {
    const sections = Array.from(document.querySelectorAll("[data-resource-pagination]"));
    sections.forEach((section) => {
      const items = Array.from(section.querySelectorAll("[data-resource]"));
      if (items.length <= pageSizeOptions[0]) return;

      const heading = section.querySelector("#resources-heading, h2, h3");
      const label = heading && heading.textContent.trim() ? heading.textContent.trim() : "Resources";
      const pager = createPager({
        containers: [
          section.querySelector("[data-pagination-bottom]"),
        ],
        label,
        pageSizeLabel: "Resources per page",
        itemName: "resource",
        itemNamePlural: "resources",
        total: () => items.length,
        renderRange: (start, end) => {
          items.forEach((item, index) => {
            item.hidden = index < start || index >= end;
          });

          Array.from(section.querySelectorAll("[data-subcategory-section]")).forEach((subsection) => {
            const hasVisibleItems = Array.from(subsection.querySelectorAll("[data-resource]")).some(
              (item) => !item.hidden
            );
            subsection.hidden = !hasVisibleItems;
          });
        },
      });
      pager.render();
    });
  }

  initializeResourcePagination();

  if (!search || !clearButton || !searchAll) return;

  let searchMatches = [];
  let searchPager = null;

  if (resultsSection && resultsList) {
    searchPager = createPager({
      containers: [
        document.querySelector("[data-search-pagination-bottom]"),
      ],
      label: "Search results",
      pageSizeLabel: "Results per page",
      itemName: "result",
      itemNamePlural: "results",
      total: () => searchMatches.length,
      renderRange: (start, end, totalCount) => {
        resultsList.replaceChildren(...searchMatches.slice(start, end).map(resultItem));
        resultsSection.hidden = false;
        const hasMatches = totalCount > 0;
        resultsList.hidden = !hasMatches;
        noResults.hidden = hasMatches;
        const noun = totalCount === 1 ? "result" : "results";
        status.textContent = hasMatches
          ? `${totalCount} ${noun} found. Showing ${start + 1} to ${end}.`
          : "0 results found.";
      },
    });
    searchPager.hide();
  }

  function siteRootUrl() {
    const root = document.body.dataset.siteRoot || "./";
    return new URL(root, window.location.href);
  }

  function itemHref(item) {
    if (/^[a-z][a-z0-9+.-]*:/i.test(item.href)) {
      return item.href;
    }
    return new URL(item.href, siteRootUrl()).href;
  }

  function selectedScopes() {
    if (searchAll.checked) return [];
    return filterBoxes.filter((box) => box.checked).map((box) => box.value);
  }

  function matchesScope(item, scopes, wholeSite) {
    if (wholeSite) return true;
    if (scopes.length === 0) return false;
    return scopes.some((scope) => item.scopes.includes(scope));
  }

  function clearResults() {
    if (!resultsSection || !resultsList || !noResults || !status) return;
    searchMatches = [];
    resultsList.replaceChildren();
    resultsList.hidden = true;
    resultsSection.hidden = true;
    noResults.hidden = true;
    status.textContent = "";
    if (searchPager) {
      searchPager.hide();
    }
  }

  function resultItem(item) {
    const listItem = document.createElement("li");
    listItem.className = "resource-item";

    const link = document.createElement("a");
    link.href = itemHref(item);
    if (item.downloadable) {
      link.setAttribute("download", item.downloadName || "");
    } else {
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
    link.textContent = item.title;
    listItem.append(link);

    if (item.fileInfo) {
      const fileInfo = document.createElement("p");
      fileInfo.className = "resource-meta";
      fileInfo.textContent = item.resultType === "resource" ? `File: ${item.fileInfo}` : item.fileInfo;
      listItem.append(fileInfo);
    }

    if (item.category) {
      const category = document.createElement("p");
      category.className = "resource-meta";
      category.textContent = item.category;
      listItem.append(category);
    }

    return listItem;
  }

  function applyUrlSearch() {
    const params = new URLSearchParams(window.location.search);
    const query = params.get("q") || "";
    const scopes = params.getAll("scope");
    const scopeSet = new Set(scopes);

    search.value = query;
    if (scopes.length > 0) {
      searchAll.checked = false;
      filterBoxes.forEach((box) => {
        box.checked = scopeSet.has(box.value);
      });
    } else {
      searchAll.checked = true;
      filterBoxes.forEach((box) => {
        box.checked = false;
      });
    }

    if (!resultsSection || !resultsList || !noResults || !status) return;

    const normalizedQuery = query.trim().toLocaleLowerCase();
    const wholeSite = scopes.length === 0;
    const hasSearch = normalizedQuery.length > 0;

    if (!hasSearch) {
      clearResults();
      return;
    }

    searchMatches = resources
      .filter((item) => {
        const textMatches = item.searchText.includes(normalizedQuery);
        return textMatches && matchesScope(item, scopes, wholeSite);
      })
      .sort((a, b) => {
        const groupDifference = (a.sortGroup || 3) - (b.sortGroup || 3);
        if (groupDifference !== 0) return groupDifference;
        return a.title.localeCompare(b.title, undefined, { sensitivity: "base" });
      });

    if (searchPager) {
      searchPager.reset();
    }
    if (window.location.hash === "#search-results-heading" && resultsHeading) {
      resultsHeading.focus();
    }
  }

  searchAll.addEventListener("change", () => {
    if (searchAll.checked) {
      filterBoxes.forEach((box) => {
        box.checked = false;
      });
    }
  });
  filterBoxes.forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) {
        searchAll.checked = false;
      }
    });
  });
  clearButton.addEventListener("click", () => {
    search.value = "";
    searchAll.checked = true;
    filterBoxes.forEach((box) => {
      box.checked = false;
    });
    clearResults();
    search.focus();
    if (resultsSection) {
      history.replaceState(null, "", window.location.pathname);
    }
  });

  if (resultsSection) {
    applyUrlSearch();
  }
})();
