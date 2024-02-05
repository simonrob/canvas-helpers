// ==UserScript==
// @name         Canvas Helpers
// @namespace    https://github.com/simonrob/canvas-helpers
// @version      2024-02-02
// @updateURL    https://github.com/simonrob/canvas-helpers/raw/main/canvashelpers.user.js
// @downloadURL  https://github.com/simonrob/canvas-helpers/raw/main/canvashelpers.user.js
// @description  A UserScript to help make common Canvas tasks more manageable
// @author       Simon Robinson
// @match        https://*.instructure.com/*
// @match        https://canvas.swansea.ac.uk/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=instructure.com
// @grant        GM_addStyle
// @run-at       document-end
// ==/UserScript==
/* global $ */

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
    `);

    // Convenience function to run a callback only after an element matching readySelector has been added to the page.
    // Gives up after 1 minute. See: https://github.com/Tampermonkey/tampermonkey/issues/1279#issuecomment-875386821
    // Example: runWhenReady('.search-result', yourCallbackFunction);
    function runWhenReady(readySelector, callback) {
        let numAttempts = 0;
        const tryNow = function () {
            const elem = document.querySelector(readySelector);
            if (elem) {
                callback(elem);
            } else {
                numAttempts++;
                if (numAttempts >= 34) {
                    logCHMessage('Giving up `runWhenReady` - could not find `' + readySelector + '`');
                } else {
                    setTimeout(tryNow, 250 * Math.pow(1.1, numAttempts));
                }
            }
        };
        tryNow();
    }

    // -----------------------------------------------------------------------------------------------------------------
    // Homepage: make course cards smaller and hide the "Published Courses" header
    // -----------------------------------------------------------------------------------------------------------------
    runWhenReady('.ic-DashboardCard__box__header', function () {
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
    });

    // -----------------------------------------------------------------------------------------------------------------
    // Group assignments: sort the list of groups by group number (ascending)
    // -----------------------------------------------------------------------------------------------------------------
    runWhenReady('#assignment-speedgrader-link select optgroup option', function () {
        logCHMessage('Sorting SpeedGrader group names');
        // Move the download button a little further away to prevent accidental clicks
        GM_addStyle(`
            #speed_grader_link_mount_point {
                margin-bottom: 3rem !important;
            }
        `);

        // Sort the option list - see: https://stackoverflow.com/a/12073377
        const options = $('select optgroup option');
        const arr = options.map(function (_, o) {
            return {
                t: $(o).text(),
                v: o.value
            };
        }).get();
        arr.sort(function (o1, o2) {
            return o1.t.localeCompare(o2.t, undefined, {
                numeric: true,
                sensitivity: 'base'
            });
        });
        options.each(function (i, o) {
            o.value = arr[i].v;
            $(o).text(arr[i].t);
        });

        // Deselect the current option (which Canvas itself caches, and ends up being mis-mapped)
        document.getElementsByTagName('select')[0].value = '';
        document.getElementsByClassName('icon-speed-grader')[0].href = '#';
    });

    // -----------------------------------------------------------------------------------------------------------------
    // Item lists: remove extra spacing around Modules, Assignments, etc like Condensed MAQ Layout, but a little less
    // aggressive (see: github.com/paulbui/canvas-tweaks)
    // -----------------------------------------------------------------------------------------------------------------
    runWhenReady('.item-group-condensed', function () {
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
    });
})();
