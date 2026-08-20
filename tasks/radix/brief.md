# Task: fix a reported bug in `radix`

## Bug report (verbatim from the project's issue tracker)
**installHook.js:1 Error: Maximum update depth exceeded - React 19 + Radix**

## Bug report

### Current Behavior

When using Radix components with React 19, an infinite loop occurs causing the error:                                                                                          
                                                                                                                                                                                 
  Error: Maximum update depth exceeded. This can happen when a component repeatedly calls setState inside componentWillUpdate or componentDidUpdate. React limits the number of  
  nested updates to prevent infinite loops.                                                                                                                                      
      at setRef (composeRefs.tsx:11:5)                                                                                                                                           
      at composeRefs.tsx:22:45                                                                                                                                                   
      at Array.forEach (<anonymous>)                                                                                                                                             
      at composeRefs.tsx:22:28                                                                                                                                                   
      at setRef (composeRefs.tsx:11:5)                                                                                                                                           
      at composeRefs.tsx:22:45                                                                                                                                                   
      ...                                                                                                                                                                        
                                                                                                                                                                                 
  The setRef function in @radix-ui/react-compose-refs recursively triggers itself, causing React to hit the maximum update depth limit.                                          
                                                                                                                                                                                 
  In React 19, ref callback behavior changed - ref callbacks can now return cleanup functions, and React may call ref callbacks differently than in React 18. When setRef calls  
  ref(value) at line 11, it triggers a re-render which invokes setRef again via the composed ref callback at line 22, creating an infinite loop.    


### Expected behavior

  Composed refs should work without causing infinite update loops in React 19.                                                                                                    

### Reproducible example

I have platejs plugins with radix popovers and radix tooltips on them. If I write fast inside plate, the page breaks. 
I'm on a Macbook M1 Pro with 32 GB. One way to trigger this error is to inspect chrome and start a performance recording and start typing real fast. On Safari, for example, it doesn't break. I tried on restarted browser, guest mode. I'm not the only one

[CodeSandbox Template](n/a)

### Suggested solution

  The composeRefs and useComposedRefs functions need to handle React 19's new ref callback behavior. Possible approaches:                                                        
                                                                                                                                                                                 
  1. Memoize the composed ref callback to prevent unnecessary re-invocations                                                                                                     
  2. Add a guard to prevent recursive setRef calls                                                                                                                               
  3. Handle the cleanup function return value from React 19 ref callbacks       

### Additional context
Right now, it works fine with react 18 (even on next.js 16+) and we had to downgrade.

I also saw this reddit post https://www.reddit.com/r/react/comments/1nnvwsp/react_19_causes_maximum_update_depth_exceeded/ where a user raised a similar case

React 19 introduced changes to ref callback behavior, including support for cleanup functions returned from ref callbacks. This may be causing the ref to be re-invoked on each render cycle.                                                                                                                                                                 
                                                                                                                                                                                 
  Related stack trace also shows Slate editor involvement:                                                                                                                       
  at Slate.useCallback[onContextChange] (slate.tsx:62:7)                                                                                                                         
  at e.onChange (with-dom.ts:371:7)                                                                                                                                              
  at with-react.ts:54:7                                                                                                                                                          
                                                                                                                                                                                 
  This suggests the issue manifests when Radix components are used alongside Slate/Plate editors, where both libraries compose refs. 

### Your environment

| Software         | Name(s)                               | Version       |
| ---------------- | ------------------------------------- | ------------- |
| Radix Package(s) | @radix-ui/react-compose-refs          | 1.1.0         |
| Radix Package(s) | @radix-ui/react-accordion             | 1.2.12        |
| Radix Package(s) | @radix-ui/react-avatar                | 1.1.11        |
| Radix Package(s) | @radix-ui/react-checkbox              | 1.3.3         |
| Radix Package(s) | @radix-ui/react-collapsible           | 1.1.12        |
| Radix Package(s) | @radix-ui/react-dialog                | 1.1.15        |
| Radix Package(s) | @radix-ui/react-dropdown-menu         | 2.1.16        |
| Radix Package(s) | @radix-ui/react-hover-card            | 1.1.15        |
| Radix Package(s) | @radix-ui/react-icons                 | 1.3.2         |
| Radix Package(s) | @radix-ui/react-popover               | 1.1.15        |
| Radix Package(s) | @radix-ui/react-progress              | 1.1.8         |
| Radix Package(s) | @radix-ui/react-select                | 2.2.6         |
| Radix Package(s) | @radix-ui/react-separator             | 1.1.8         |
| Radix Package(s) | @radix-ui/react-toolbar               | 1.1.11        |
| Radix Package(s) | @radix-ui/react-tooltip               | 1.2.8         |
| React            | react, @types/react                   | 19.2.3        |
| Browser          | Chrome                                | Latest        |
| Assistive tech   | n/a                                   |               |
| Node             | node                                  | 24.13.0       |
| npm/yarn/pnpm    | pnpm                                  | 10.26.0       |
| Operating System | macOS                                 | Darwin 24.6.0 |


  - Next.js: 16.1.1                                                                                                                                                              
  - TypeScript: 5.9.3                                                                                                                                                            
  - platejs: 52.0.15

## Standing instructions (identical for every run)
You are working in the repository at the current working directory. Work like a careful open-source contributor:
1. Reproduce the bug first (write a minimal failing test or script) before changing code.
2. Find the root cause; fix the cause, not the symptom. Keep the change minimal and in the project's style.
3. Add or update a regression test that fails before your fix and passes after.
4. Run the project's test suite and make it green. Do not modify or delete unrelated tests.
5. When done, summarize: root cause, the files you changed, how you verified it.
Do not ask me for permission between steps; proceed until the task is complete, then report.

Test command for this repo: `pnpm vitest run packages/react/slot`
