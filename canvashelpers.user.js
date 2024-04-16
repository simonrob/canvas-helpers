// ==UserScript==
// @name         Canvas Helpers
// @namespace    https://github.com/simonrob/canvas-helpers
// @version      2024-04-16
// @updateURL    https://github.com/simonrob/canvas-helpers/raw/main/canvashelpers.user.js
// @downloadURL  https://github.com/simonrob/canvas-helpers/raw/main/canvashelpers.user.js
// @require      https://gist.githubusercontent.com/raw/51e2fe655d4d602744ca37fa124869bf/GM_addStyle.js
// @require      https://gist.githubusercontent.com/raw/86cbf1fa9f24f7d821632e9c1ca96571/waitForKeyElements.js
// @description  A UserScript to help make common Canvas tasks more manageable
// @author       Simon Robinson
// @match        https://*.instructure.com/*
// @match        https://canvas.swansea.ac.uk/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=instructure.com
// @grant        none
// @run-at       document-end
// ==/UserScript==
/* global GM_addStyle, waitForKeyElements */

(function () {
    'use strict';

    // Convenience function for consistency (and easier filtering) in logged messages
    function logCHMessage(message) {
        console.log('Canvas Helpers UserScript: ' + message);
    }

    GM_addStyle(`
        body:not(.full-width):not(.outcomes):not(.body--login-confirmation) .ic-Layout-wrapper {
            max-width: inherit !important; /* for some reason the beta and test pages have this set to 1366px */
        }
        #right-side .shared-space h2 {
            display: inline; /* fix the display of inline icons in right-side menus */
        }
    `);

    // remove the courses popout menu and just go straight to the list (Canvancement's "All Courses Sort" recommended)
    const allCourses = document.getElementById('global_nav_courses_link');
    if (allCourses) {
        allCourses.onclick = function () {
            window.location.href = this.href;
            return false;
        };
    }

    // add a new button to clear all todo list items
    waitForKeyElements('.todo-list-header', function (header) {
        const headerWrapper = document.createElement('div');
        headerWrapper.setAttribute('class', 'h2 shared-space');
        headerWrapper.setAttribute('style', 'margin-top: 18px;');
        const clearIcon = document.createElement('a');
        clearIcon.setAttribute('class', 'events-list icon-trash standalone-icon');
        clearIcon.setAttribute('style', 'float: right; font-size: 12px; font-size: 0.75rem; font-weight: normal;');
        clearIcon.setAttribute('href', '#');
        clearIcon.addEventListener('click', function () {
            const todoList = document.querySelectorAll('button[title="Ignore until new submission"]');
            [...todoList].forEach(button => {
                button.click();
            });
            return false;
        });
        clearIcon.textContent = 'Clear all';
        header.parentNode.insertBefore(headerWrapper, header);
        headerWrapper.appendChild(header);
        headerWrapper.appendChild(clearIcon);
    });

    // for the Python-based New Quiz integrations, we need a separate API key - make retrieving this easier
    waitForKeyElements('div[role="main"] > div', function (container) {
        const headerContainer = container.querySelector('.pages-styles__preHeaderContent');
        if (headerContainer) {
            headerContainer.insertAdjacentHTML('beforeend', '<button id="canvas-helpers-quiz-api-key" ' +
                'style="cursor:pointer" type="button"><span>Display New Quiz API token</span></button>');
            headerContainer.querySelector('#canvas-helpers-quiz-api-key').addEventListener('click', function () {
                alert(window.sessionStorage.access_token);
            });
        }
    });

    // -----------------------------------------------------------------------------------------------------------------
    // Homepage: make course cards smaller and hide the "Published Courses" header (in staff view)
    // -----------------------------------------------------------------------------------------------------------------
    if (['', '/dashboard'].includes(window.location.pathname.replace(/\/$/, ''))) {
        logCHMessage('Resizing card list and removing main header');
        GM_addStyle(`
            .ic-Layout-contentMain {
                padding: 30px 0px 42px 30px;
            }
            @media only screen and (min-width: 992px) {
                body:not(.course-menu-expanded) .ic-app-main-content__secondary {
                    width:190px;
                    padding-left:12px;
                }
            }
            .ic-DashboardCard {
                width: 192px !important;
                padding-bottom: 12px;
            }
            .ic-DashboardCard__header_hero {
                height: 106px !important;
            }
            .ic-DashboardCard__header-subtitle {
                font-size: 75% !important;
            }
            .ic-DashboardCard__header-term, .ic-DashboardCard__action-container {
                display: none !important;
            }
            .ic-DashboardCard__box:first-child > .ic-DashboardCard__box__header {
                display: none;
            }
            .unpublished_courses_redesign .ic-DashboardCard__box {
                padding: 12px 0;
            }
        `);
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Item lists: remove extra spacing around Modules, Assignments, etc like Condensed MAQ Layout, but a little less
    // aggressive (see: https://github.com/paulbui/canvas-tweaks)
    // -----------------------------------------------------------------------------------------------------------------
    if (window.location.pathname.startsWith('/courses')) {
        logCHMessage('Removing spacing around list items');
        GM_addStyle(`
            .item-group-condensed .ig-header {
                padding : 3px 0 !important;
                margin-top: 0px !important;
            }
            .ig-list .ig-row {
                padding: 2px 0 !important;
            }
            .ig-list {
                font-size : 0.9rem !important;
            }
            .locked_title {
                font-size : 1rem !important;
            }
        `);
    }
})();
